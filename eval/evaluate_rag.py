from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from app.services.rag import run_rag_pipeline


STRICT_MODE = True


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

    total = 0
    hits = 0

    for item in golden_data:
        query = str(item.get("query") or "").strip()
        expected_file = str(item.get("expected_file") or "").strip()

        if not query or not expected_file:
            continue

        total += 1
        _, retrieved_chunks = run_rag_pipeline(query)

        # Strict mode uses only pipeline output to reflect true end-to-end performance.
        if not STRICT_MODE:
            from app.services.rag import retrieve_relevant_chunks

            if not retrieved_chunks:
                retrieved_chunks = retrieve_relevant_chunks(query=query, top_k=5)

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
