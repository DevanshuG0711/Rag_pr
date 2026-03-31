import re

from app.services.embeddings import generate_embeddings
from app.services.vector_store import search_similar_chunks


def keyword_score(query: str, text: str) -> int:
    query_words = set(re.findall(r"\b\w+\b", query.lower()))
    text_words = set(re.findall(r"\b\w+\b", text.lower()))
    return len(query_words & text_words)


def hybrid_search(query: str, top_k: int) -> list[dict[str, object]]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    query_embedding = generate_embeddings(chunks=[query])[0]
    semantic_results = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=top_k * 2,
    )

    rescored_results: list[dict[str, object]] = []
    for result in semantic_results:
        semantic_score = float(result.get("score", 0.0))
        text = str(result.get("chunk_text") or "")
        kw_score = keyword_score(query=query, text=text)
        final_score = semantic_score + (0.1 * kw_score)

        updated = dict(result)
        updated["score"] = final_score
        rescored_results.append(updated)

    rescored_results.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return rescored_results[:top_k]
