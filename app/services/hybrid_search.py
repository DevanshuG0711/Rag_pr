import re

from app.services.embeddings import generate_embeddings
from app.services.vector_store import search_similar_chunks

RRF_K = 60


def keyword_score(query: str, text: str) -> int:
    query_words = set(re.findall(r"\b\w+\b", query.lower()))
    text_words = set(re.findall(r"\b\w+\b", text.lower()))
    return len(query_words & text_words)


def _result_key(result: dict[str, object]) -> str:
    file_name = str(result.get("file_name") or "")
    chunk_index = result.get("chunk_index")

    if file_name and chunk_index is not None:
        return f"{file_name}:{chunk_index}"

    return str(result.get("id") or "")


def _rrf_score(rank: int, k: int = RRF_K) -> float:
    return 1.0 / (k + rank)


def hybrid_search(query: str, top_k: int) -> list[dict[str, object]]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    query_embedding = generate_embeddings(chunks=[query])[0]
    semantic_results = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=top_k * 5,
    )

    if not semantic_results:
        return []

    semantic_ranked = sorted(
        semantic_results,
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )

    keyword_ranked = sorted(
        semantic_results,
        key=lambda item: keyword_score(query, str(item.get("chunk_text") or "")),
        reverse=True,
    )

    rrf_totals: dict[str, float] = {}
    representatives: dict[str, dict[str, object]] = {}

    for rank, result in enumerate(semantic_ranked, start=1):
        key = _result_key(result)
        if not key:
            continue
        representatives[key] = dict(result)
        rrf_totals[key] = rrf_totals.get(key, 0.0) + _rrf_score(rank)

    for rank, result in enumerate(keyword_ranked, start=1):
        key = _result_key(result)
        if not key:
            continue
        if key not in representatives:
            representatives[key] = dict(result)
        rrf_totals[key] = rrf_totals.get(key, 0.0) + _rrf_score(rank)

    fused = sorted(rrf_totals.items(), key=lambda item: item[1], reverse=True)

    scored_results: list[dict[str, object]] = []
    for key, score in fused:
        result = dict(representatives[key])
        result["score"] = score
        scored_results.append(result)

    unique_results: list[dict[str, object]] = []
    seen_chunk_keys: set[tuple[str, object]] = set()

    for result in scored_results:
        chunk_key = (str(result.get("file_name") or ""), result.get("chunk_index"))
        if chunk_key in seen_chunk_keys:
            continue

        unique_results.append(result)
        seen_chunk_keys.add(chunk_key)

        if len(unique_results) >= top_k:
            break

    return unique_results
