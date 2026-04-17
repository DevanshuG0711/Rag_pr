import os
import re
import json
import logging
from typing import List, Dict
from typing import Literal
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError

from app.services.call_graph import extract_call_graph
from app.services.call_graph_query import build_graph
from app.services.call_graph_query import expand_with_graph
from app.services.call_graph_query import get_callees
from app.services.call_graph_query import get_callers
from app.services.call_graph_query import get_all_call_graph
from app.services.call_graph_query import get_call_graph_for_file
from app.services.hybrid_search import hybrid_search
from app.services.query_classifier import classify_query
from app.services.embeddings import generate_embeddings
from app.services.vector_store import fetch_all_chunks_by_file
from app.services.vector_store import search_similar_chunks_by_file
from app.services.vector_store import fetch_chunks_by_function_names


logger = logging.getLogger(__name__)
FLOW_QUERY_TERMS = ("flow", "calls", "called by", "dependency")
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3"
CONTEXT_MAX_TOKENS = 1200
QUERY_TYPO_FIXES = {
	"funtion": "function",
	"fuction": "function",
	"fucntion": "function",
	"cal": "call",
	"clal": "call",
	"caal": "call",
	"cals": "calls",
	"clls": "calls",
}


def _is_ollama_available() -> bool:
	url = f"{OLLAMA_BASE_URL}/api/tags"

	try:
		with urllib_request.urlopen(url, timeout=2.0) as response:
			return response.status == 200
	except (URLError, HTTPError, TimeoutError):
		return False


def _normalize_query_for_intent(query: str) -> str:
	normalized = query.lower()

	for typo, correction in QUERY_TYPO_FIXES.items():
		normalized = re.sub(rf"\b{re.escape(typo)}\b", correction, normalized)

	# Normalize call variants like call/calls/calling/called to a stable token.
	normalized = re.sub(r"\bcall(?:s|ed|ing)?\b", "calls", normalized)
	normalized = re.sub(r"\s+", " ", normalized).strip()
	return normalized


def _has_call_keyword(normalized_query: str) -> bool:
	return re.search(r"\bcall[a-z]*\b", normalized_query) is not None


def _is_graph_forced_query(query: str) -> bool:
	normalized_query = _normalize_query_for_intent(query)
	return (
		_has_call_keyword(normalized_query)
		or re.search(r"\bfunction\b", normalized_query) is not None
		or re.search(r"\bwho\b", normalized_query) is not None
	)


def _detect_graph_query_mode(query: str) -> Literal["none", "caller", "callee", "flow"]:
	normalized_query = _normalize_query_for_intent(query)

	if "flow" in normalized_query or "dependency" in normalized_query:
		return "flow"

	if "what does" in normalized_query and _has_call_keyword(normalized_query):
		return "callee"

	if "who calls" in normalized_query or "which function calls" in normalized_query:
		return "caller"

	if _is_graph_forced_query(query):
		return "flow"

	return "none"


def _extract_caller_query_target(query: str) -> str:
	normalized_query = _normalize_query_for_intent(query)

	patterns = [
		r"\bwho calls\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
		r"\bwhich function calls\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
	]

	for pattern in patterns:
		match = re.search(pattern, normalized_query)
		if match:
			return match.group(1)

	return ""


def _extract_usage_query_target(query: str) -> str:
	normalized_query = _normalize_query_for_intent(query)

	patterns = [
		r"\bwho calls\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
		r"\bwhich function calls\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
		r"\bwhat does\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+calls?\b",
	]

	for pattern in patterns:
		match = re.search(pattern, normalized_query)
		if match:
			return match.group(1)

	return ""


def _is_whole_file_query(query: str) -> bool:
	normalized = _normalize_query_for_intent(query)
	return any(
		phrase in normalized
		for phrase in (
			"explain whole code",
			"explain this file",
			"what does this file do",
		)
	)


def retrieve_relevant_chunks(
	query: str,
	top_k: int = 5,
	file_name: str | None = None,
	mode: str = "global",
) -> list[dict[str, object]]:
	if mode == "file_only":
		normalized_file_name = str(file_name or "").strip()
		if not normalized_file_name:
			return []

		if _is_whole_file_query(query):
			return fetch_all_chunks_by_file(normalized_file_name)

		query_embedding = generate_embeddings(chunks=[query])[0]
		return search_similar_chunks_by_file(
			query_embedding=query_embedding,
			file_name=normalized_file_name,
			top_k=max(1, top_k),
		)

	query_type = classify_query(query)

	if query_type == "explain":
		effective_top_k = 8
	else:
		effective_top_k = 5
	
	print("query_type:", query_type, "top_k:", effective_top_k)

	logger.info("query_type=%s effective_top_k=%s", query_type, effective_top_k)

	return hybrid_search(query=query, top_k=effective_top_k)


def _unique_chunk_key(chunk: dict[str, object]) -> str:
	file_name = str(chunk.get("file_name") or "")
	chunk_index = chunk.get("chunk_index")
	chunk_id = str(chunk.get("id") or "")

	if file_name and chunk_index is not None:
		return f"{file_name}:{chunk_index}"
	if chunk_id:
		return chunk_id
	return str(chunk.get("chunk_text") or "")


def _merge_dedup_chunks(original: list[dict[str, object]], extra: list[dict[str, object]]) -> list[dict[str, object]]:
	merged: list[dict[str, object]] = []
	seen: set[str] = set()

	for chunk in [*original, *extra]:
		key = _unique_chunk_key(chunk)
		if key in seen:
			continue
		seen.add(key)
		merged.append(chunk)

	return merged


def _expand_chunks_with_call_graph(
	query: str,
	retrieved_chunks: list[dict[str, object]],
	max_depth: int = 1,
	mode: str = "global",
	file_name: str | None = None,
) -> list[dict[str, object]]:
	if not retrieved_chunks:
		return []

	graph_mode = _detect_graph_query_mode(query)
	if graph_mode == "none":
		return retrieved_chunks

	file_names = list(
		dict.fromkeys(
			str(chunk.get("file_name") or "").strip()
			for chunk in retrieved_chunks
			if str(chunk.get("file_name") or "").strip()
		)
	)

	merged_graph: dict[str, list[str]] = {}
	for chunk_file_name in file_names:
		try:
			graph = get_call_graph_for_file(file_name=chunk_file_name)
		except Exception:
			graph = {}

		for func_name, callees in graph.items():
			existing = merged_graph.get(func_name, [])
			for callee in callees:
				if callee not in existing:
					existing.append(callee)
			merged_graph[func_name] = existing

	if not merged_graph:
		return retrieved_chunks

	build_graph(merged_graph)

	initial_function_names = [
		str(chunk.get("name") or "").strip()
		for chunk in retrieved_chunks
		if str(chunk.get("type") or "") == "function" and str(chunk.get("name") or "").strip()
	]

	expanded_function_names: list[str] = []

	if graph_mode == "caller":
		caller_target = _extract_caller_query_target(query)
		targets = [caller_target] if caller_target else list(initial_function_names)
		expanded_function_names = list(targets)
		for target in targets:
			expanded_function_names.extend(get_callers(target))
		expanded_function_names = list(dict.fromkeys(expanded_function_names))
	elif graph_mode == "callee":
		expanded_function_names = list(initial_function_names)
		for target in initial_function_names:
			expanded_function_names.extend(get_callees(target))
		expanded_function_names = list(dict.fromkeys(expanded_function_names))
	elif graph_mode == "flow":
		expanded_function_names = expand_with_graph(
			initial_function_names,
			max_depth=max(2, max_depth),
		)

	if not expanded_function_names:
		return retrieved_chunks

	expanded_chunks = fetch_chunks_by_function_names(
		function_names=expanded_function_names,
		file_names=file_names,
	)

	fetched_function_names = {
		str(chunk.get("name") or "").strip()
		for chunk in expanded_chunks
		if str(chunk.get("name") or "").strip()
	}

	missing_function_names = [
		name
		for name in expanded_function_names
		if name not in fetched_function_names
	]

	if missing_function_names and mode == "global":
		fallback_chunks = fetch_chunks_by_function_names(
			function_names=missing_function_names,
			file_names=None,
		)
		expanded_chunks = _merge_dedup_chunks(expanded_chunks, fallback_chunks)

	if mode == "file_only":
		normalized_file_name = str(file_name or "").strip()
		if normalized_file_name:
			expanded_chunks = [
				chunk
				for chunk in expanded_chunks
				if str(chunk.get("file_name") or "").strip() == normalized_file_name
			]

	return _merge_dedup_chunks(retrieved_chunks, expanded_chunks)


def build_context(chunks: list[dict[str, object]]) -> str:
	if not chunks:
		return ""

	def _estimate_tokens(text: str) -> int:
		return len(text) // 4

	def _format_chunk(idx: int, chunk: dict[str, object]) -> str:
		file_name = str(chunk.get("file_name") or "unknown")
		start_line = chunk.get("start_line")
		end_line = chunk.get("end_line")
		if start_line is not None and end_line is not None:
			line_info = f"{start_line}-{end_line}"
		else:
			chunk_index = chunk.get("chunk_index")
			line_info = f"chunk-{chunk_index}" if chunk_index is not None else "N/A"
		chunk_text = str(chunk.get("chunk_text") or "")

		return "\n".join(
			[
				f"[Chunk {idx}]",
				f"File: {file_name}",
				f"Lines: {line_info}",
				"Code:",
				chunk_text,
				"",
			]
		)

	parts: list[str] = ["=== Context ===", ""]
	token_count = _estimate_tokens("\n".join(parts))

	for idx, chunk in enumerate(chunks, start=1):
		chunk_block = _format_chunk(idx=idx, chunk=chunk)
		chunk_tokens = _estimate_tokens(chunk_block)

		# Always include the first chunk, even if it exceeds budget.
		if idx > 1 and token_count + chunk_tokens > CONTEXT_MAX_TOKENS:
			break

		parts.append(chunk_block)
		token_count += chunk_tokens
	

	return "\n".join(parts).rstrip()


def _build_query_aware_graph_context(
	query: str,
	graph: dict[str, list[str]],
	retrieved_chunks: list[dict[str, object]],
) -> str:
	if not graph:
		return ""

	mode = _detect_graph_query_mode(query)
	if mode == "none":
		return ""

	build_graph(graph)
	target_functions = list(
		dict.fromkeys(
			str(chunk.get("name") or "").strip()
			for chunk in retrieved_chunks
			if str(chunk.get("type") or "") == "function" and str(chunk.get("name") or "").strip()
		)
	)

	if mode == "caller":
		caller_target = _extract_caller_query_target(query)
		if caller_target:
			target_functions = [caller_target]

	if not target_functions:
		return ""

	relations: list[str] = []

	if mode == "caller":
		for target in target_functions:
			for caller in get_callers(target):
				relations.append(f"{caller} calls {target}")
	elif mode == "callee":
		for target in target_functions:
			for callee in get_callees(target):
				relations.append(f"{target} calls {callee}")
	else:
		expanded = expand_with_graph(target_functions, max_depth=2)
		expanded_set = set(expanded)
		for caller, callees in graph.items():
			if caller not in expanded_set:
				continue
			for callee in callees:
				if callee in expanded_set:
					relations.append(f"{caller} calls {callee}")

	relations = list(dict.fromkeys(relations))
	if not relations:
		return ""

	header = "Flow:" if mode == "flow" else "Relationships:"
	return "\n".join([header, *relations])


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


def _build_flow_from_db(graph: dict[str, list[str]]) -> str:
	lines = ["Flow:"]
	for func, called in graph.items():
		if called:
			lines.append(f"{func} calls {', '.join(called)}")

	if len(lines) == 1:
		return ""

	return "\n".join(lines)


def _extract_flow_edges(graph_lines: list[str]) -> list[tuple[str, str]]:
	edges: list[tuple[str, str]] = []
	for raw_line in graph_lines:
		line = str(raw_line).strip()
		if not line:
			continue

		match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+calls\s+(.+)$", line)
		if not match:
			continue

		caller = match.group(1).strip()
		callees_part = match.group(2).strip()
		callees = [name.strip() for name in callees_part.split(",") if name.strip()]
		for callee in callees:
			edges.append((caller, callee))

	# Keep insertion order and remove duplicates.
	return list(dict.fromkeys(edges))


def _generate_flow_explanation_rule_based(graph_lines: list[str]) -> str:
	edges = _extract_flow_edges(graph_lines)
	if not edges:
		return "No call relationships found."

	adjacency: dict[str, list[str]] = {}
	indegree: dict[str, int] = {}
	for caller, callee in edges:
		adjacency.setdefault(caller, []).append(callee)
		indegree.setdefault(caller, 0)
		indegree[callee] = indegree.get(callee, 0) + 1

	starts = [node for node in adjacency if indegree.get(node, 0) == 0]
	if not starts:
		starts = [edges[0][0]]

	seen_edges: set[tuple[str, str]] = set()
	chains: list[list[str]] = []

	def build_chain(start: str) -> list[str]:
		chain = [start]
		current = start
		while True:
			options = [
				nxt
				for nxt in adjacency.get(current, [])
				if (current, nxt) not in seen_edges
			]
			if not options:
				break

			nxt = options[0]
			seen_edges.add((current, nxt))
			chain.append(nxt)
			current = nxt

			# Stop chain on branch points to keep text concise and readable.
			remaining = [
				c for c in adjacency.get(current, []) if (current, c) not in seen_edges
			]
			if len(remaining) > 1:
				break

		return chain

	for start in starts:
		if len(chains) >= 3:
			break
		chain = build_chain(start)
		if len(chain) >= 2:
			chains.append(chain)

	# Cover remaining unseen edges as short statements.
	for caller, callee in edges:
		if len(chains) >= 5:
			break
		if (caller, callee) in seen_edges:
			continue
		seen_edges.add((caller, callee))
		chains.append([caller, callee])

	sentences: list[str] = []
	for chain in chains[:5]:
		if len(chain) == 2:
			sentences.append(f"The {chain[0]} function calls {chain[1]}.")
			continue

		base = f"The {chain[0]} function calls {chain[1]}"
		for node in chain[2:]:
			base += f", which further calls {node}"
		sentences.append(base + ".")

	if not sentences:
		return "No call relationships found."

	return "\n".join(sentences[:5])


def generate_flow_explanation(graph_lines: list[str]) -> str:
	edges = _extract_flow_edges(graph_lines)
	if not edges:
		return "No call relationships found."

	if _is_ollama_available():
		try:
			url = f"{OLLAMA_BASE_URL}/api/generate"
			flow_text = "\n".join(f"{caller} calls {callee}" for caller, callee in edges)
			prompt = (
				"You are a code assistant. Convert function-call edges into a concise, human-readable explanation.\n"
				"Rules:\n"
				"- Return only explanation text.\n"
				"- Use simple English.\n"
				"- Merge connected steps and avoid repetition.\n"
				"- Keep output concise: 3 to 5 lines maximum.\n\n"
				"Edges:\n"
				f"{flow_text}\n"
			)

			payload = {
				"model": OLLAMA_MODEL,
				"prompt": prompt,
				"stream": False,
			}
			data = json.dumps(payload).encode("utf-8")
			req = urllib_request.Request(
				url,
				data=data,
				headers={"Content-Type": "application/json"},
				method="POST",
			)

			with urllib_request.urlopen(req, timeout=20.0) as response:
				if response.status == 200:
					body = json.loads(response.read().decode("utf-8"))
					text = str(body.get("response") or "").strip()
					if text:
						lines = [line.strip() for line in text.splitlines() if line.strip()]
						return "\n".join(lines[:5])
		except Exception:
			pass

	return _generate_flow_explanation_rule_based([f"{caller} calls {callee}" for caller, callee in edges])


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


def _generate_with_ollama(query: str, context: str) -> str:
	url = f"{OLLAMA_BASE_URL}/api/generate"
	prompt = (
		"You are a code assistant.\n"
		"Use the provided context to answer the question clearly and concisely.\n\n"
		"Context:\n"
		f"{context}\n\n"
		"Question:\n"
		f"{query}\n"
	)
	payload = {
		"model": OLLAMA_MODEL,
		"prompt": prompt,
		"stream": True,
	}
	data = json.dumps(payload).encode("utf-8")
	req = urllib_request.Request(
		url,
		data=data,
		headers={"Content-Type": "application/json"},
		method="POST",
	)

	parts: list[str] = []

	try:
		with urllib_request.urlopen(req, timeout=30.0) as response:
			if response.status != 200:
				raise ValueError(f"Ollama returned status {response.status}")

			for raw_line in response:
				line = raw_line.decode("utf-8").strip()
				if not line:
					continue

				try:
					chunk = json.loads(line)
				except json.JSONDecodeError:
					continue

				if "error" in chunk:
					raise ValueError(f"Ollama error: {chunk['error']}")

				piece = chunk.get("response")
				if piece:
					parts.append(str(piece))
	except (URLError, HTTPError, TimeoutError) as exc:
		raise ValueError("Failed to reach Ollama") from exc

	final_text = "".join(parts).strip()
	if not final_text:
		raise ValueError("Ollama returned an empty response")

	return final_text



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
            if "Flow:" in line:
                capture = True
                continue

            if capture:
                if line.strip() == "":
                    continue
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
			if _is_ollama_available():
				try:
					return _generate_with_ollama(query=query, context=context)
				except Exception:
					return _generate_local_answer(query=query, context=context, chunks=chunks)
			return _generate_local_answer(query=query, context=context, chunks=chunks)

	if _is_ollama_available():
		try:
			return _generate_with_ollama(query=query, context=context)
		except Exception:
			return _generate_local_answer(query=query, context=context, chunks=chunks)

	return _generate_local_answer(query=query, context=context, chunks=chunks)


def run_rag_pipeline(
	query: str,
	top_k: int = 5,
	file_name: str | None = None,
	repo_indexed: bool = False,
) -> tuple[str, list[dict[str, object]]]:
	if str(file_name or "").strip():
		mode = "file_only"
	elif repo_indexed:
		mode = "global"
	else:
		mode = "global"

	print("MODE:", mode)
	print("FILE:", file_name)

	query_type = classify_query(query)
	effective_mode = "file_only" if mode == "file_only" and str(file_name or "").strip() else "global"
	normalized_file_name = str(file_name or "").strip() or None

	if query_type == "find_usage":
		target = _extract_usage_query_target(query)
		if not target:
			return "No target function found in query.", []

		if effective_mode == "file_only" and normalized_file_name:
			graph = get_call_graph_for_file(file_name=normalized_file_name)
		else:
			graph = get_all_call_graph()
		if not graph:
			return "No call graph data available.", []

		build_graph(graph)
		normalized_query = _normalize_query_for_intent(query)
		if re.search(r"\bwhat does\b", normalized_query):
			callees = get_callees(target)
			if not callees:
				return f"No callees found for {target}.", []
			return "\n".join(f"{target} calls {callee}" for callee in callees), []

		callers = get_callers(target)
		if not callers:
			return f"No callers found for {target}.", []
		return "\n".join(f"{caller} calls {target}" for caller in callers), []

	if query_type == "flow":
		if effective_mode == "file_only" and normalized_file_name:
			graph = get_call_graph_for_file(file_name=normalized_file_name)
		else:
			graph = get_all_call_graph()
		if not graph:
			return "No call graph data available.", []

		build_graph(graph)
		normalized_query = _normalize_query_for_intent(query)
		seeds = [name for name in graph if re.search(rf"\b{re.escape(name.lower())}\b", normalized_query)]
		expanded = expand_with_graph(seeds if seeds else list(graph.keys()), max_depth=2)
		expanded_set = set(expanded)

		lines: list[str] = []
		for caller, callees in graph.items():
			if caller not in expanded_set:
				continue
			for callee in callees:
				if callee in expanded_set:
					lines.append(f"{caller} calls {callee}")

		if not lines:
			return "No call relationships found.", []

		return generate_flow_explanation(lines), []

	retrieved_chunks = retrieve_relevant_chunks(
		query=query,
		top_k=top_k,
		mode=effective_mode,
		file_name=normalized_file_name,
	)
	retrieved_chunks = _expand_chunks_with_call_graph(
		query=query,
		retrieved_chunks=retrieved_chunks,
		max_depth=1,
		mode=effective_mode,
		file_name=normalized_file_name,
	)
	context = build_context(retrieved_chunks)

	if query_type == "search":
		answer = _generate_local_answer(query=query, context=context, chunks=retrieved_chunks)
		return answer, retrieved_chunks

	# explain
	answer = generate_answer(query=query, context=context, chunks=retrieved_chunks)
	return answer, retrieved_chunks
