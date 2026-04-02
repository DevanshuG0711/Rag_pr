from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

from app.services.chunking import chunk_text
from app.services.embeddings import generate_embeddings
from app.services.ingest import extract_code_chunks
from app.services.vector_store import get_qdrant_client
from app.services.vector_store import search_similar_chunks
from app.services.vector_store import store_chunk_embeddings


class QueryCase(TypedDict):
    query: str
    expected_function: str


def _load_query_cases(queries_file: str | None) -> list[QueryCase]:
    if queries_file is None:
        return [
            {"query": "How does login work?", "expected_function": "login"},
            {"query": "Where is user validation done?", "expected_function": "validate_user"},
            {"query": "Which function checks database?", "expected_function": "db_check"},
        ]

    raw = json.loads(Path(queries_file).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("queries file must contain a JSON list")

    cases: list[QueryCase] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"query item at index {index} must be an object")
        query = str(item.get("query") or "").strip()
        expected = str(item.get("expected_function") or "").strip()
        if not query or not expected:
            raise ValueError(
                "each query item must include non-empty 'query' and 'expected_function'"
            )
        cases.append({"query": query, "expected_function": expected})

    return cases


def _contains_expected(results: list[dict[str, object]], expected_function: str) -> bool:
    needle = expected_function.lower()
    for result in results:
        text = str(result.get("chunk_text") or "").lower()
        if needle in text:
            return True
    return False


def _evaluate(
    collection_name: str,
    chunks: list[str],
    file_name: str,
    top_k: int,
    query_cases: list[QueryCase],
) -> float:
    if not chunks:
        return 0.0

    embeddings = generate_embeddings(chunks=chunks)
    store_chunk_embeddings(
        file_name=file_name,
        chunks=chunks,
        embeddings=embeddings,
        collection_name=collection_name,
    )

    correct = 0
    for case in query_cases:
        query_embedding = generate_embeddings(chunks=[case["query"]])[0]
        results = search_similar_chunks(
            query_embedding=query_embedding,
            top_k=top_k,
            collection_name=collection_name,
        )
        if _contains_expected(results, case["expected_function"]):
            correct += 1

    return correct / len(query_cases)


def _delete_collection_if_exists(collection_name: str) -> None:
    client = get_qdrant_client()
    if client.collection_exists(collection_name=collection_name):
        client.delete_collection(collection_name=collection_name)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare naive chunking vs AST chunking retrieval accuracy"
    )
    parser.add_argument("file_path", help="Path to a source code file (.py/.js/.ts/.go)")
    parser.add_argument(
        "--queries-file",
        help="Path to JSON file: [{\"query\": str, \"expected_function\": str}]",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=500)
    parser.add_argument("--overlap", type=int, default=50)
    args = parser.parse_args()

    if args.top_k <= 0:
        raise ValueError("--top-k must be greater than 0")

    source_path = Path(args.file_path)
    code = source_path.read_text(encoding="utf-8")
    query_cases = _load_query_cases(args.queries_file)

    naive_chunks = chunk_text(text=code, chunk_size=args.chunk_size, overlap=args.overlap)
    ast_chunks, _ = extract_code_chunks(code=code, file_name=source_path.name)

    naive_collection = f"eval_naive_{uuid4().hex[:8]}"
    ast_collection = f"eval_ast_{uuid4().hex[:8]}"

    try:
        accuracy_naive = _evaluate(
            collection_name=naive_collection,
            chunks=naive_chunks,
            file_name=source_path.name,
            top_k=args.top_k,
            query_cases=query_cases,
        )
        accuracy_ast = _evaluate(
            collection_name=ast_collection,
            chunks=ast_chunks,
            file_name=source_path.name,
            top_k=args.top_k,
            query_cases=query_cases,
        )
    finally:
        _delete_collection_if_exists(naive_collection)
        _delete_collection_if_exists(ast_collection)

    print(f"accuracy_naive: {accuracy_naive:.3f}")
    print(f"accuracy_ast: {accuracy_ast:.3f}")


if __name__ == "__main__":
    main()
