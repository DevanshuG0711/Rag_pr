import math
import re
from collections import Counter

from sentence_transformers import CrossEncoder

from app.services.embeddings import generate_embeddings
from app.services.vector_store import search_similar_chunks, get_qdrant_client
from qdrant_client.http.models import Filter

RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75
CROSS_ENCODER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MAX_RERANK_CANDIDATES = 20
MIN_RERANK_CANDIDATES = 10

_cross_encoder_model: CrossEncoder | None = None


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


def _get_cross_encoder_model() -> CrossEncoder:
    global _cross_encoder_model

    if _cross_encoder_model is None:
        _cross_encoder_model = CrossEncoder(CROSS_ENCODER_MODEL_NAME)

    return _cross_encoder_model


def _rerank_with_cross_encoder(query: str, candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    if not candidates:
        return []

    model = _get_cross_encoder_model()
    pairs = [(query, str(item.get("chunk_text") or "")) for item in candidates]
    scores = model.predict(pairs)

    reranked: list[dict[str, object]] = []
    for item, score in zip(candidates, scores):
        updated = dict(item)
        updated["score"] = float(score)
        reranked.append(updated)

    reranked.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return reranked


def _get_all_chunks() -> list[dict[str, object]]:
    try:
        client = get_qdrant_client()
        all_results = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name="documents",
                scroll_filter=Filter(),
                limit=256,
                with_payload=True,
                offset=offset,
            )
            if not points:
                break
            for point in points:
                payload = getattr(point, "payload", None) or {}
                all_results.append({
                    "id": str(getattr(point, "id", "")),
                    "file_name": payload.get("file_name"),
                    "chunk_index": payload.get("chunk_index"),
                    "chunk_text": payload.get("chunk_text"),
                    "name": payload.get("name"),
                    "type": payload.get("type"),
                    "start_line": payload.get("start_line"),
                    "end_line": payload.get("end_line"),
                    "docstring": payload.get("docstring") or "",
                    "imports": payload.get("imports", []),
                })
            if offset is None:
                break
        return all_results
    except Exception:
        return []


def hybrid_search(query: str, top_k: int) -> list[dict[str, object]]:
    if top_k <= 0:
        raise ValueError("top_k must be greater than 0")

    # Fix 4: Add safety check for empty embeddings
    embeddings = generate_embeddings(chunks=[query])
    if not embeddings:
        return []
    query_embedding = embeddings[0]

    semantic_results = search_similar_chunks(
        query_embedding=query_embedding,
        top_k=top_k * 3,  # Fix 3: Reduce fetch size to top_k * 3
    )

    all_chunks = _get_all_chunks()
    
    if not all_chunks:
        return semantic_results[:top_k]

    # Fix 1: Normalize semantic results
    normalized_semantic = []
    for item in semantic_results:
        normalized_semantic.append({
            "id": str(item.get("id", "")),
            "file_name": item.get("file_name"),
            "chunk_index": item.get("chunk_index"),
            "chunk_text": item.get("chunk_text"),
            "name": item.get("name"),
            "type": item.get("type"),
            "start_line": item.get("start_line"),
            "end_line": item.get("end_line"),
            "docstring": item.get("docstring") or "",
            "imports": item.get("imports", []),
            "score": float(item.get("score", 0.0)),
        })

    semantic_ranked = sorted(
        normalized_semantic,
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )

    chunk_texts = [str(item.get("chunk_text") or "") for item in all_chunks]
    keyword_scores = bm25_scores(query=query, documents=chunk_texts)
    
    # Fix 2: Normalize BM25 scores to [0,1]
    max_score = max(keyword_scores) if keyword_scores else 1.0
    if max_score == 0.0:
        max_score = 1.0
    keyword_scores = [score / max_score for score in keyword_scores]

    indexed_keyword_results = list(enumerate(all_chunks))

    keyword_ranked = [
        item
        for _, item in sorted(
            indexed_keyword_results,
            key=lambda pair: keyword_scores[pair[0]],
            reverse=True,
        )
    ][:top_k * 3]  # Fix 3: Reduce fetch size to top_k * 3

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

    rerank_pool_size = min(max(top_k * 4, MIN_RERANK_CANDIDATES), MAX_RERANK_CANDIDATES)
    rerank_candidates = unique_results[:rerank_pool_size]

    try:
        reranked_results = _rerank_with_cross_encoder(query=query, candidates=rerank_candidates)
    except Exception:
        reranked_results = rerank_candidates

    return reranked_results[:top_k]
