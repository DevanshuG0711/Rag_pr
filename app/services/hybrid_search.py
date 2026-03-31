import math
import re
from collections import Counter

from app.services.embeddings import generate_embeddings
from app.services.vector_store import search_similar_chunks

RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def bm25_scores(query: str, documents: list[str]) -> list[float]:
    if not documents:
        return []

    query_terms = list(set(_tokenize(query)))
    tokenized_docs = [_tokenize(doc) for doc in documents]
    doc_lengths = [len(tokens) for tokens in tokenized_docs]
    avg_doc_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 0.0

    doc_freq: dict[str, int] = {}
    for tokens in tokenized_docs:
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    doc_term_counts = [Counter(tokens) for tokens in tokenized_docs]
    n_docs = len(documents)
    scores: list[float] = []

    for doc_index, term_counts in enumerate(doc_term_counts):
        score = 0.0
        doc_len = doc_lengths[doc_index]

        for term in query_terms:
            tf = term_counts.get(term, 0)
            if tf == 0:
                continue

            df = doc_freq.get(term, 0)
            idf = math.log(((n_docs - df + 0.5) / (df + 0.5)) + 1.0)

            norm = BM25_K1 * (1 - BM25_B + BM25_B * (doc_len / avg_doc_len)) if avg_doc_len > 0 else BM25_K1
            score += idf * (tf * (BM25_K1 + 1)) / (tf + norm)

        scores.append(score)

    return scores


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

    chunk_texts = [str(item.get("chunk_text") or "") for item in semantic_results]
    keyword_scores = bm25_scores(query=query, documents=chunk_texts)

    indexed_keyword_results = list(enumerate(semantic_results))

    keyword_ranked = [
        item
        for _, item in sorted(
            indexed_keyword_results,
            key=lambda pair: keyword_scores[pair[0]],
            reverse=True,
        )
    ]

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
