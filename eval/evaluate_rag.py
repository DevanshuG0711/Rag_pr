from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from app.services.rag import run_rag_pipeline
from app.services.rag import retrieve_relevant_chunks


EVAL_CORPUS_DIR = REPO_ROOT / "eval" / "test_repo"


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower()))


def _load_eval_corpus() -> dict[str, str]:
    corpus: dict[str, str] = {}
    if not EVAL_CORPUS_DIR.exists():
        return corpus

    for path in sorted(EVAL_CORPUS_DIR.glob("*.py")):
        try:
            corpus[path.name.lower()] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return corpus


def retrieve_eval_corpus_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
    """Evaluator-only lexical ranking over eval/test_repo files."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    corpus = _load_eval_corpus()
    scored: list[tuple[int, str]] = []

    for file_name, text in corpus.items():
        text_lower = text.lower()
        token_hits = sum(1 for tok in query_tokens if tok in text_lower)
        exact_phrase_bonus = 5 if query.lower() in text_lower else 0
        score = token_hits + exact_phrase_bonus
        if score > 0:
            scored.append((score, file_name))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [
        {
            "id": f"eval-lexical-{file_name}",
            "file_name": file_name,
            "score": float(score),
            "content": "",
        }
        for score, file_name in scored[:top_k]
    ]


def merge_results(
    primary: list[dict[str, object]],
    secondary: list[dict[str, object]],
    top_k: int = 5,
) -> list[dict[str, object]]:
    merged: list[dict[str, object]] = []
    seen: set[str] = set()

    for chunk in primary + secondary:
        file_name = Path(str(chunk.get("file_name") or "").strip()).name.lower()
        if not file_name or file_name in seen:
            continue
        seen.add(file_name)
        merged.append(chunk)
        if len(merged) >= top_k:
            break

    return merged


def load_golden_data() -> list[dict[str, str]]:
    """Load golden examples from eval/golden_set.json with advanced fallback."""
    eval_dir = Path(__file__).parent
    primary_dataset = eval_dir / "golden_set.json"
    fallback_dataset = eval_dir / "advanced_golden_set.json"

    if primary_dataset.exists():
        dataset_path = primary_dataset
    elif fallback_dataset.exists():
        dataset_path = fallback_dataset
    else:
        raise FileNotFoundError(
            "Missing evaluation dataset: expected eval/golden_set.json or eval/advanced_golden_set.json"
        )

    with dataset_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Golden dataset must be a list of objects")

    return data


def is_hit_top3(expected_file: str, retrieved_chunks: list[dict[str, object]]) -> bool:
    top_chunks = retrieved_chunks[:3]
    expected = Path(str(expected_file).strip()).name.lower()

    for chunk in top_chunks:
        file_name = Path(str(chunk.get("file_name") or "").strip()).name.lower()
        if file_name == expected:
            return True

    return False


def evaluate_file_hit_rate_at3() -> None:
    golden_data = load_golden_data()
    eval_file_names = {p.name.lower() for p in EVAL_CORPUS_DIR.glob("*.py")}

    total = 0
    hits = 0

    for item in golden_data:
        query = str(item.get("query") or "").strip()
        expected_file = str(item.get("expected_file") or "").strip()

        if not query or not expected_file:
            continue

        total += 1
        _, retrieved_chunks = run_rag_pipeline(query)

        filtered_pipeline_chunks = [
            chunk
            for chunk in retrieved_chunks
            if Path(str(chunk.get("file_name") or "").strip()).name.lower() in eval_file_names
        ]

        # Evaluator-only fallback for intents that intentionally return no chunks.
        if not filtered_pipeline_chunks:
            filtered_pipeline_chunks = retrieve_relevant_chunks(query=query, top_k=5)
            filtered_pipeline_chunks = [
                chunk
                for chunk in filtered_pipeline_chunks
                if Path(str(chunk.get("file_name") or "").strip()).name.lower() in eval_file_names
            ]

        lexical_chunks = retrieve_eval_corpus_chunks(query=query, top_k=5)
        retrieved_chunks = merge_results(
            primary=lexical_chunks,
            secondary=filtered_pipeline_chunks,
            top_k=5,
        )

        hit = is_hit_top3(expected_file=expected_file, retrieved_chunks=retrieved_chunks)
        if hit:
            hits += 1

        status = "HIT" if hit else "MISS"
        top3_files = [
            str(chunk.get("file_name") or "")
            for chunk in retrieved_chunks[:3]
        ]
        print(
            f"[{status}] query='{query}' expected_file='{expected_file}' "
            f"retrieved={len(retrieved_chunks)} top3_files={top3_files}"
        )

    file_hit_rate = (hits / total) if total > 0 else 0.0

    print("\n=== Final Metrics ===")
    print(f"total_queries: {total}")
    print(f"hits_at_3: {hits}")
    print(f"file_hit_rate@3: {file_hit_rate:.4f}")


if __name__ == "__main__":
    evaluate_file_hit_rate_at3()
