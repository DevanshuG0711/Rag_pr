import os
import re
import logging
from typing import List, Dict

from app.services.call_graph import extract_call_graph
from app.services.hybrid_search import hybrid_search
from app.services.query_classifier import classify_query


logger = logging.getLogger(__name__)
FLOW_QUERY_TERMS = ("flow", "calls", "called by", "dependency")


def retrieve_relevant_chunks(query: str, top_k: int = 5) -> list[dict[str, object]]:
	query_type = classify_query(query)

	if query_type == "explain":
		effective_top_k = 8
	else:
		effective_top_k = 5
	
	print("query_type:", query_type, "top_k:", effective_top_k)

	logger.info("query_type=%s effective_top_k=%s", query_type, effective_top_k)

	return hybrid_search(query=query, top_k=effective_top_k)


def build_context(chunks: list[dict[str, object]]) -> str:
	if not chunks:
		return ""

	parts: list[str] = ["=== Context ===", ""]
	for idx, chunk in enumerate(chunks[:5], start=1):
		file_name = str(chunk.get("file_name") or "unknown")
		start_line = chunk.get("start_line")
		end_line = chunk.get("end_line")
		if start_line is not None and end_line is not None:
			line_info = f"{start_line}-{end_line}"
		else:
			chunk_index = chunk.get("chunk_index")
			line_info = f"chunk-{chunk_index}" if chunk_index is not None else "N/A"
		chunk_text = str(chunk.get("chunk_text") or "")

		parts.extend(
			[
				f"[Chunk {idx}]",
				f"File: {file_name}",
				f"Lines: {line_info}",
				"Code:",
				chunk_text,
				"",
			]
		)

	return "\n".join(parts).rstrip()


def _is_flow_query(query: str) -> bool:
	query_lower = query.lower()
	return any(term in query_lower for term in FLOW_QUERY_TERMS)


def _build_flow_context(chunks: list[dict[str, object]]) -> str:
	merged_graph: dict[str, list[str]] = {}

	for chunk in chunks[:5]:
		chunk_text = str(chunk.get("chunk_text") or "")
		if not chunk_text.strip():
			continue

		try:
			chunk_graph = extract_call_graph(chunk_text)
		except Exception:
			continue

		for func, called_funcs in chunk_graph.items():
			existing = merged_graph.get(func, [])
			for called in called_funcs:
				if called not in existing:
					existing.append(called)
			merged_graph[func] = existing

	lines: list[str] = ["Flow:"]
	for func, called_funcs in merged_graph.items():
		if not called_funcs:
			continue
		lines.append(f"{func} calls {', '.join(called_funcs)}")

	if len(lines) == 1:
		return ""

	return "\n".join(lines)


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

	user_prompt = (
		"You are a code assistant.\n"
		"Use the provided context to answer the question.\n\n"
		"Context:\n"
		f"{context}\n\n"
		"Question:\n"
		f"{query}\n\n"
		"Answer clearly and concisely."
	)

	response = client.responses.create(
		model=model_name,
		input=user_prompt,
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

# def _generate_local_answer(query: str, chunks: List[Dict[str, object]]) -> str:
#     if not chunks:
#         return "I could not find relevant context."

#     import re

#     def clean_words(text):
#         return set(re.findall(r'\b\w+\b', text.lower()))

#     top_chunks = chunks[:3]
#     combined_text = " ".join(str(c.get("chunk_text") or "") for c in top_chunks)

#     # FIXED split
#     sentences = re.split(r'(?<=[.!?])\s+', combined_text.strip())

#     query_words = clean_words(query)

#     def score(sentence):
#         return len(clean_words(sentence) & query_words)

#     ranked = sorted(sentences, key=score, reverse=True)

#     best = [s for s in ranked if score(s) > 0][:1]
	
#     if not best:
#         best = sentences[:1]

#     return "Local Answer: " + " ".join(best)

# The above function tries to extract the most relevant sentences from the top 3 chunks based on keyword overlap with the query. This is a simple heuristic that can provide a more informative answer than just taking the top chunk's text.

## Further improved local answer generation with flow detection and explanation. #
def _generate_local_answer(
    query: str,
    context: str,
    chunks: List[Dict[str, object]]
) -> str:
    if not chunks:
        return "I could not find relevant context."

    import re

    query_lower = query.lower()

    # 🔥 STEP 1: FLOW DETECTION
    if any(word in query_lower for word in ["flow", "call", "depend"]):
        lines = context.splitlines()

        flow_lines = []
        capture = False

        for line in lines:
            if line.strip().startswith("Flow:"):
                capture = True
                continue

            if capture:
                if not line.strip():
                    break
                flow_lines.append(line.strip())

        if flow_lines:
            return "Flow Explanation:\n" + "\n".join(flow_lines)

    # 🔥 STEP 2: OLD LOGIC (unchanged)
    def clean_words(text):
        return set(re.findall(r'\b\w+\b', text.lower()))

    top_chunks = chunks[:3]
    combined_text = " ".join(str(c.get("chunk_text") or "") for c in top_chunks)

    sentences = re.split(r'(?<=[.!?])\s+', combined_text.strip())
    query_words = clean_words(query)

    def score(sentence):
        return len(clean_words(sentence) & query_words)

    ranked = sorted(sentences, key=score, reverse=True)
    best = [s for s in ranked if score(s) > 0][:1]

    if not best:
        best = sentences[:1]

    return "Local Answer: " + " ".join(best)

# The updated _generate_local_answer function first checks if the query is likely asking about the flow of function calls. If it detects flow-related terms, it tries to extract and return the flow explanation from the context. If not, it falls back to the original keyword-based sentence extraction method. This way, we can provide a more relevant answer for flow-related queries without needing an LLM.

def generate_answer(query: str, context: str, chunks: list[dict[str, object]]) -> str:
	if os.getenv("OPENAI_API_KEY"):
		try:
			return _generate_with_openai(query=query, context=context)
		except Exception:
			return _generate_local_answer(query=query, context=context, chunks=chunks)

	return _generate_local_answer(query=query, context=context, chunks=chunks)


def run_rag_pipeline(query: str, top_k: int = 5) -> tuple[str, list[dict[str, object]]]:
	retrieved_chunks = retrieve_relevant_chunks(query=query, top_k=top_k)
	context = build_context(retrieved_chunks)

	if _is_flow_query(query):
		flow_context = _build_flow_context(retrieved_chunks)
		if flow_context:
			context = f"{context}\n\n{flow_context}" if context else flow_context

	print(context)
	answer = generate_answer(query=query, context=context, chunks=retrieved_chunks)
	return answer, retrieved_chunks
