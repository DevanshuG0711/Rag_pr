import os
import re
from typing import List, Dict

from app.services.embeddings import generate_embeddings
from app.services.vector_store import search_similar_chunks


def retrieve_relevant_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
	query_embedding = generate_embeddings(chunks=[query])[0]
	return search_similar_chunks(query_embedding=query_embedding, top_k=top_k)


def build_context(chunks: list[dict[str, object]]) -> str:
	if not chunks:
		return ""

	parts: list[str] = []
	for idx, chunk in enumerate(chunks, start=1):
		file_name = str(chunk.get("file_name") or "unknown")
		chunk_index = chunk.get("chunk_index")
		chunk_text = str(chunk.get("chunk_text") or "")
		parts.append(
			f"[{idx}] file={file_name} chunk_index={chunk_index}\n{chunk_text}"
		)

	return "\n\n".join(parts)


def _generate_with_openai(query: str, context: str) -> str:
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise ValueError("OPENAI_API_KEY is not set")

	try:
		from openai import OpenAI
	except ImportError as exc:
		raise ValueError("openai package is not installed") from exc

	model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
	client = OpenAI(api_key=api_key)

	system_prompt = (
		"You are a helpful assistant answering questions only from provided context. "
		"If context is insufficient, say that clearly."
	)
	user_prompt = (
		"Context:\n"
		f"{context if context else 'No context found.'}\n\n"
		"Question:\n"
		f"{query}\n\n"
		"Answer briefly and accurately."
	)

	response = client.responses.create(
		model=model_name,
		input=[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_prompt},
		],
	)

	return response.output_text.strip()


# def _generate_local_answer(query: str, chunks: list[dict[str, object]]) -> str:
# 	if not chunks:
# 		return "I could not find relevant context to answer this question."

# 	top_chunk_text = str(chunks[0].get("chunk_text") or "")
# 	return (
# 		"Local fallback answer (no OpenAI key configured). "
# 		f"Best matching context says: {top_chunk_text}"
# 	)

## Improved local answer generation without LLM, using simple keyword matching and sentence extraction. #

def _generate_local_answer(query: str, chunks: List[Dict[str, object]]) -> str:
    if not chunks:
        return "I could not find relevant context to answer this question."

    # Step 1: Take top 3 chunks (instead of 1)
    top_chunks = chunks[:3]

    # Step 2: Combine text
    combined_text = " ".join(str(chunk.get("chunk_text") or "") for chunk in top_chunks)

    # Step 3: Break into sentences
    sentences = re.split(r'(?<=[.!?]) +', combined_text)

    # Step 4: Filter relevant sentences using query keywords
    query_words = set(query.lower().split())

    def score(sentence):
        words = set(sentence.lower().split())
        return len(query_words & words)

    ranked_sentences = sorted(sentences, key=score, reverse=True)

    # Step 5: Pick top relevant sentences
    best_sentences = [s for s in ranked_sentences if score(s) > 0][:3]

    if not best_sentences:
        best_sentences = sentences[:2]  # fallback

    # Step 6: Create final answer
    answer = " ".join(best_sentences)

    return f"Local Answer (fallback mode): {answer}"

# The above function tries to extract the most relevant sentences from the top 3 chunks based on keyword overlap with the query. This is a simple heuristic that can provide a more informative answer than just taking the top chunk's text.

def generate_answer(query: str, context: str, chunks: list[dict[str, object]]) -> str:
	try:
		return _generate_with_openai(query=query, context=context)
	except Exception:
		return _generate_local_answer(query=query, chunks=chunks)


def run_rag_pipeline(query: str, top_k: int = 5) -> tuple[str, list[dict[str, object]]]:
	retrieved_chunks = retrieve_relevant_chunks(query=query, top_k=top_k)
	context = build_context(retrieved_chunks)
	answer = generate_answer(query=query, context=context, chunks=retrieved_chunks)
	return answer, retrieved_chunks
