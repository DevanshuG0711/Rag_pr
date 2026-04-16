from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for evaluation runs."""
    parser = argparse.ArgumentParser(description="Evaluate RAG quality with RAGAS")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N valid queries",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Top-k passed to run_rag_pipeline when supported",
    )
    return parser.parse_args()


def load_golden_data() -> list[dict[str, Any]]:
    """Load eval dataset from golden_set.json, fallback to goldenset.json."""
    eval_dir = Path(__file__).parent
    primary_path = eval_dir / "golden_set.json"
    fallback_path = eval_dir / "goldenset.json"

    dataset_path = primary_path if primary_path.exists() else fallback_path
    if not dataset_path.exists():
        raise FileNotFoundError(
            "Dataset not found. Expected eval/golden_set.json or eval/goldenset.json"
        )

    with dataset_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Golden dataset must be a list of objects")

    return data


def build_contexts(retrieved_chunks: list[dict[str, Any]]) -> list[str]:
    """Build RAGAS contexts from retrieved chunk payloads."""
    contexts: list[str] = []

    for chunk in retrieved_chunks or []:
        chunk_text = str(chunk.get("chunk_text") or "").strip()
        if chunk_text:
            contexts.append(chunk_text)

    return contexts


def build_ragas_rows(
    golden_data: list[dict[str, Any]],
    limit: int | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Run pipeline per query and build rows for RAGAS dataset."""
    from app.services.rag import run_rag_pipeline
    from app.services.rag import retrieve_relevant_chunks

    rows: list[dict[str, Any]] = []

    for item in golden_data:
        if limit is not None and len(rows) >= limit:
            break

        if not isinstance(item, dict):
            continue

        query = str(item.get("query") or "").strip()
        if not query:
            continue

        answer, retrieved_chunks = run_rag_pipeline(query=query, top_k=top_k)
        if not retrieved_chunks:
            # Keep pipeline untouched; this is evaluator-side fallback only.
            retrieved_chunks = retrieve_relevant_chunks(query=query, top_k=top_k)

        contexts = build_contexts(retrieved_chunks=retrieved_chunks)

        row: dict[str, Any] = {
            "question": query,
            "answer": str(answer or "").strip(),
            "contexts": contexts,
        }

        # Optional references for metrics that require ground truth.
        reference = str(
            item.get("reference")
            or item.get("ground_truth")
            or item.get("expected_answer")
            or ""
        ).strip()
        if reference:
            row["reference"] = reference

        rows.append(row)

        print(
            f"[{len(rows)}] query='{query}' retrieved_chunks={len(retrieved_chunks or [])}"
        )

    return rows


def main() -> None:
    args = parse_args()

    try:
        from datasets import Dataset
    except ImportError:
        print("Missing dependency: datasets")
        print("Install with: pip install ragas datasets")
        sys.exit(1)

    try:
        from ragas import evaluate
        from ragas.embeddings import embedding_factory
        from ragas.llms import llm_factory
        from ragas.metrics.collections.answer_relevancy import AnswerRelevancy
        from ragas.metrics.collections.context_precision import (
            ContextPrecisionWithReference,
            ContextPrecisionWithoutReference,
        )
        from ragas.metrics.collections.faithfulness import Faithfulness
    except ImportError:
        print("Missing dependency: ragas")
        print("Install with: pip install ragas datasets")
        sys.exit(1)

    golden_data = load_golden_data()
    rows = build_ragas_rows(golden_data=golden_data, limit=args.limit, top_k=args.top_k)

    if not rows:
        print("No valid rows to evaluate.")
        return

    dataset = Dataset.from_list(rows)

    eval_provider = os.getenv("RAGAS_EVAL_PROVIDER", "openai")
    eval_model = os.getenv("RAGAS_EVAL_MODEL", "gpt-4o-mini")
    eval_embedding_model = os.getenv(
        "RAGAS_EVAL_EMBEDDING_MODEL", "text-embedding-3-small"
    )

    try:
        factory_kwargs: dict[str, Any] = {"provider": eval_provider}

        if eval_provider == "openai":
            openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
            if not openai_api_key:
                print("OPENAI_API_KEY is required for RAGAS evaluation with provider=openai")
                sys.exit(1)

            from openai import OpenAI

            openai_client = OpenAI(api_key=openai_api_key)
            factory_kwargs["client"] = openai_client

        eval_llm = llm_factory(model=eval_model, **factory_kwargs)
        eval_embeddings = embedding_factory(
            model=eval_embedding_model,
            **factory_kwargs,
        )
    except Exception as exc:
        print(f"Failed to initialize RAGAS evaluator models: {exc}")
        print("Set environment variables for evaluation, for example:")
        print("OPENAI_API_KEY=...")
        print("RAGAS_EVAL_PROVIDER=openai")
        print("RAGAS_EVAL_MODEL=gpt-4o-mini")
        print("RAGAS_EVAL_EMBEDDING_MODEL=text-embedding-3-small")
        sys.exit(1)

    has_reference = any("reference" in row and str(row["reference"]).strip() for row in rows)
    metrics = [
        Faithfulness(llm=eval_llm),
        AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings),
    ]
    if has_reference:
        metrics.append(ContextPrecisionWithReference(llm=eval_llm))
    else:
        print("Note: 'reference' not found in golden set. Using context precision without reference.")
        metrics.append(ContextPrecisionWithoutReference(llm=eval_llm))

    try:
        result = evaluate(dataset, metrics=metrics)
    except ValueError as exc:
        # Safety net for version-specific schema checks.
        print(f"Metric validation warning: {exc}")
        print("Retrying with faithfulness + answer_relevancy only.")
        result = evaluate(
            dataset,
            metrics=[
                Faithfulness(llm=eval_llm),
                AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings),
            ],
        )
    except Exception as exc:
        print(f"RAGAS evaluation failed: {exc}")
        print("Make sure evaluator model dependencies are configured for RAGAS.")
        sys.exit(1)

    # RAGAS returns an object with .to_dict() in many versions.
    # Fallback to plain dict casting when needed.
    if hasattr(result, "to_dict"):
        score_map = result.to_dict()
    else:
        score_map = dict(result)

    print("\n=== RAGAS Average Scores ===")
    print(f"faithfulness: {float(score_map.get('faithfulness', 0.0)):.4f}")
    print(f"answer_relevancy: {float(score_map.get('answer_relevancy', 0.0)):.4f}")
    if "context_precision" in score_map:
        print(f"context_precision: {float(score_map.get('context_precision', 0.0)):.4f}")
    if "context_precision_without_reference" in score_map:
        print(
            "context_precision: "
            f"{float(score_map.get('context_precision_without_reference', 0.0)):.4f}"
        )


if __name__ == "__main__":
    main()
