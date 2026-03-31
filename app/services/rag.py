import os
import re
from typing import List, Dict

from app.services.hybrid_search import hybrid_search


def retrieve_relevant_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
	return hybrid_search(query=query, top_k=top_k)


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
        return "I could not find relevant context."

    import re

    def clean_words(text):
        return set(re.findall(r'\b\w+\b', text.lower()))

    top_chunks = chunks[:3]
    combined_text = " ".join(str(c.get("chunk_text") or "") for c in top_chunks)

    # FIXED split
    sentences = re.split(r'(?<=[.!?])\s+', combined_text.strip())

    query_words = clean_words(query)

    def score(sentence):
        return len(clean_words(sentence) & query_words)

    ranked = sorted(sentences, key=score, reverse=True)

    best = [s for s in ranked if score(s) > 0][:1]
	
    if not best:
        best = sentences[:1]

    return "Local Answer: " + " ".join(best)

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
