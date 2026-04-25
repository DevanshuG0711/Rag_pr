from app.services.vector_store import fetch_chunks_by_function_names
from app.services.vector_store import search_similar_chunks_by_file
from app.services.vector_store import fetch_all_chunks_by_file
from app.services.tls_http import format_tls_error
from app.services.embeddings import generate_embeddings
from app.services.query_classifier import classify_query
from app.services.hybrid_search import hybrid_search
from app.services.call_graph_query import get_call_graph_for_file
from app.services.call_graph_query import get_all_call_graph
from app.services.call_graph_query import get_callers
from app.services.call_graph_query import get_callees
from app.services.call_graph_query import expand_with_graph
from app.services.call_graph_query import build_graph
import certifi
import ssl
import os
import psutil
import re
import json
import logging
from typing import List, Dict
from typing import Literal
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv

load_dotenv()


ssl._create_default_https_context = ssl.create_default_context
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()


logger = logging.getLogger(__name__)
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
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


def log_memory(stage: str):
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 * 1024)
    print(f"[MEMORY] {stage}: {mem:.2f} MB")


def detect_query_target_file(query: str) -> str | None:
    normalized = str(query or "").strip()
    if not normalized:
        return None

    direct_match = re.search(r"\b([a-zA-Z0-9_./\-]+\.(?:py|js|ts|go))\b", normalized, flags=re.IGNORECASE)
    if direct_match:
        return direct_match.group(1)

    explain_match = re.search(r"\bexplain\s+([a-zA-Z0-9_./\-]+\.(?:py|js|ts|go))\s+file\b", normalized, flags=re.IGNORECASE)
    if explain_match:
        return explain_match.group(1)

    return None


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
        r"\bcalled by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\bfunctions? called by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\bcalled inside\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\binside\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
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
        r"\bcalled by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\bfunctions? called by\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\bcalled inside\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\binside\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
        r"\bwhere is\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+used\b",
        r"\busage of\s+([a-zA-Z_][a-zA-Z0-9_]*)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized_query)
        if match:
            return match.group(1)

    return ""


def _is_usage_like_query(query: str) -> bool:
    normalized_query = _normalize_query_for_intent(query)
    return (
        re.search(r"\bwhere is\s+[a-zA-Z_][a-zA-Z0-9_]*\s+used\b", normalized_query) is not None
        or re.search(r"\busage of\s+[a-zA-Z_][a-zA-Z0-9_]*\b", normalized_query) is not None
    )


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


def _is_broad_or_vague_query(query: str) -> bool:
    normalized = _normalize_query_for_intent(query)
    patterns = [
        r"\bhow is\b",
        r"\bhow does\b",
        r"\bwhy\b",
        r"\bexplain\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def _get_llm_provider() -> str:
    return str(os.getenv("LLM_PROVIDER", "groq")).strip().lower()


def _log_generation_route(route_type: str) -> None:
    pass

def _is_noise_file(file_name: str) -> bool:
    lowered = file_name.lower()
    return any(x in lowered for x in ["config", "eslint", "tailwind", "package", ".json", ".md", "setup.", "lock", "dist", "build"])


def _adjust_score(original_score: float, weight: float) -> float:
    return original_score + weight


def _apply_heuristic_reranking(chunks: list[dict[str, object]], top_k: int, is_vague: bool, query: str = "") -> list[dict[str, object]]:
    filtered_chunks = []
    query_lower = query.lower()
    for chunk in chunks:
        fname = str(chunk.get("file_name", ""))
        lowered = fname.lower()

        if lowered and lowered in query_lower:
            weight = 50.0  # Massive boost for explicitly requested file
        elif _is_noise_file(fname):
            if is_vague:
                continue
            weight = -5.0
        elif lowered.endswith((".py", ".go")):
            weight = 2.0
        elif lowered.endswith((".js", ".ts", ".jsx", ".tsx")):
            weight = 1.0
        else:
            weight = 0.0

        original_score = float(chunk.get("score", 0.0) or 0.0)
        chunk["heuristic_score"] = _adjust_score(original_score, weight)
        filtered_chunks.append(chunk)

    filtered_chunks.sort(key=lambda x: float(
        x.get("heuristic_score", -999.0)), reverse=True)

    max_per_file = 2 if is_vague else 3
    final_chunks = []
    file_counts = {}

    for chunk in filtered_chunks:
        fname = str(chunk.get("file_name", ""))
        
        # Lift the cap if this file was explicitly queried for
        effective_max = 999 if fname and fname.lower() in query_lower else max_per_file
        
        if file_counts.get(fname, 0) < effective_max:
            final_chunks.append(chunk)
            file_counts[fname] = file_counts.get(fname, 0) + 1
        if len(final_chunks) >= top_k:
            break

    return final_chunks


def retrieve_relevant_chunks(
        query: str,
        top_k: int = 5,
        file_name: str | None = None,
        mode: str = "global",
) -> list[dict[str, object]]:
    detected_files = re.findall(
        r'\b[a-zA-Z0-9_\-]+\.(?:py|js|ts|tsx|jsx|go|md|json)\b', query)
    if detected_files and mode != "file_only" and not file_name:
        mode = "file_only"
        file_name = detected_files[0]

    if mode == "file_only":
        normalized_file_name = str(file_name or "").strip()
        if not normalized_file_name:
            return []

        if _is_whole_file_query(query):
            return fetch_all_chunks_by_file(normalized_file_name)

        try:
            embeddings = generate_embeddings(chunks=[query])
            if not embeddings:
                return []
            query_embedding = embeddings[0]
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            return []

        return search_similar_chunks_by_file(
            query_embedding=query_embedding,
            file_name=normalized_file_name,
            top_k=max(1, top_k),
        )

    query_type = classify_query(query)
    effective_top_k = max(1, top_k)
    is_vague = _is_broad_or_vague_query(query)

    logger.debug("query_type=%s top_k=%s is_vague=%s",
                 query_type, effective_top_k, is_vague)

    fetch_k = effective_top_k * 3 if is_vague else effective_top_k * 2
    raw_chunks = hybrid_search(query=query, top_k=fetch_k)

    return _apply_heuristic_reranking(raw_chunks, effective_top_k, is_vague, query)


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


def _file_name_matches_target(target_file: str, chunk_file_name: str | None) -> bool:
    if not chunk_file_name:
        return False

    target_file = str(target_file or "").lower().strip()
    chunk_file = str(chunk_file_name or "").lower().strip()
    if not target_file or not chunk_file:
        return False

    target_base = os.path.basename(target_file).lower().strip()
    chunk_base = os.path.basename(chunk_file).lower().strip()
    if chunk_base == target_base:
        return True

    return chunk_file.endswith(target_file)


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
        targets = [caller_target] if caller_target else list(
            initial_function_names)
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
                if _file_name_matches_target(
                    target_file=normalized_file_name,
                    chunk_file_name=chunk.get("file_name"),
                )
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
        callees = [name.strip()
                   for name in callees_part.split(",") if name.strip()]
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

    flow_text = "\n".join(
        f"{caller} calls {callee}" for caller, callee in edges)
    flow_context = (
        "Convert function-call edges into a concise, human-readable explanation.\n"
        "Return only explanation text with 3 to 5 lines max.\n\n"
        f"Edges:\n{flow_text}"
    )

    if not os.getenv("GROQ_API_KEY"):
        return _generate_flow_explanation_rule_based([f"{caller} calls {callee}" for caller, callee in edges])

    try:
        text = _generate_with_groq(
            query="Explain this call flow.", context=flow_context)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            return "\n".join(lines[:5])
    except Exception as exc:
        logger.warning("Groq flow generation failed: %s, falling back to local rule-based explanation", exc)

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


def _generate_with_groq(query: str, context: str) -> str:
    api_key = str(os.getenv("GROQ_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    user_content = (
        "Context:\n"
        f"{context}\n\n"
        "Question:\n"
        f"{query}\n\n"
        "Answer clearly and concisely."
    )

    model_name = str(os.getenv("GROQ_MODEL", GROQ_MODEL)).strip() or GROQ_MODEL
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful code assistant."},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        GROQ_BASE_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "python-requests/2.31.0",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=30.0) as response:
            if response.status != 200:
                raise ValueError(f"Groq returned status {response.status}")

            body = json.loads(response.read().decode("utf-8"))
            content = str(
                (
                    body.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            ).strip()
            if not content:
                raise ValueError("Groq returned an empty response")
            return content
    except HTTPError as exc:
        error_detail = format_tls_error(exc)
        logger.warning("Groq request failed: %s", error_detail)
        raise ValueError(f"Failed to reach Groq: {error_detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        error_detail = format_tls_error(exc)
        logger.warning("Groq request failed: %s", error_detail)
        raise ValueError(f"Failed to reach Groq: {error_detail}") from exc


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
    combined_text = " ".join(str(c.get("chunk_text") or "")
                             for c in top_chunks)

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
    provider = _get_llm_provider()

    if provider == "openai":
        try:
            return _generate_with_openai(query=query, context=context)
        except Exception as exc:
            logger.warning("OpenAI generation failed: %s, falling back to local generation", exc)
            return _generate_local_answer(query=query, context=context, chunks=chunks)
    elif provider == "groq":
        if not os.getenv("GROQ_API_KEY"):
            return _generate_local_answer(query=query, context=context, chunks=chunks)
        try:
            return _generate_with_groq(query=query, context=context)
        except Exception as exc:
            logger.warning("Groq generation failed: %s, falling back to local generation", exc)
            return _generate_local_answer(query=query, context=context, chunks=chunks)

    return _generate_local_answer(query=query, context=context, chunks=chunks)


def run_rag_pipeline(
        query: str,
        top_k: int = 5,
        file_name: str | None = None,
        repo_indexed: bool = False,
) -> tuple[str, list[dict[str, object]]]:
    if repo_indexed:
        mode = "global"
        file_name = None
    elif str(file_name or "").strip():
        mode = "file_only"
    else:
        mode = "global"

    logger.debug("mode=%s file=%s", mode, file_name)

    query_type = classify_query(query)
    if _is_usage_like_query(query):
        query_type = "find_usage"
    effective_mode = "file_only" if mode == "file_only" and str(
        file_name or "").strip() else "global"
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
            logger.info(
                "Call graph unavailable for find_usage query; falling back to standard RAG path")
        else:
            build_graph(graph)
            normalized_query = _normalize_query_for_intent(query)
            if re.search(r"\bwhat does\b", normalized_query):
                found_callees = []
                for node, callees in graph.items():
                    if str(node).split("::")[-1] == target:
                        for callee in callees:
                            c_base = str(callee).split("::")[-1]
                            c_file = str(callee).split("::")[0] if "::" in str(callee) else "unknown"
                            found_callees.append(f"- {c_file} -> {c_base}()")
                
                if found_callees:
                    return f"The function {target} calls:\n" + "\n".join(list(dict.fromkeys(found_callees))), []
                return "No usage found in the indexed repository", []

            found_callers = []
            for node, callees in graph.items():
                n_base = str(node).split("::")[-1]
                n_file = str(node).split("::")[0] if "::" in str(node) else "unknown"
                for callee in callees:
                    if str(callee).split("::")[-1] == target:
                        found_callers.append(f"- {n_file} -> {n_base}()")
            
            if found_callers:
                return f"The function {target} is used in:\n" + "\n".join(list(dict.fromkeys(found_callers))), []
            return "No usage found in the indexed repository", []

    if query_type == "flow":
        if effective_mode == "file_only" and normalized_file_name:
            graph = get_call_graph_for_file(file_name=normalized_file_name)
        else:
            graph = get_all_call_graph()
        if not graph:
            logger.info(
                "Call graph unavailable for flow query; falling back to standard RAG path")
        else:
            build_graph(graph)
            normalized_query = _normalize_query_for_intent(query)
            seeds = []
            for name in graph:
                name_base = str(name).split("::", 1)[-1]
                if re.search(rf"\b{re.escape(name_base.lower())}\b", normalized_query):
                    seeds.append(name)
            expanded = expand_with_graph(
                seeds if seeds else list(graph.keys()), max_depth=2)
            expanded_set = set(expanded)

            steps = []
            step_count = 1
            seen_edges = set()
            for caller, callees in graph.items():
                caller_base = str(caller).split("::", 1)[-1]
                if caller_base not in expanded_set:
                    continue
                for callee in callees:
                    callee_base = str(callee).split("::", 1)[-1]
                    if callee_base in expanded_set:
                        edge = (caller_base, callee_base)
                        if edge not in seen_edges:
                            seen_edges.add(edge)
                            if step_count == 1:
                                steps.append(f"Step {step_count}: {caller_base}() is called")
                                step_count += 1
                            steps.append(f"Step {step_count}: {caller_base}() calls {callee_base}()")
                            step_count += 1

            if not steps:
                return "No usage found in the indexed repository", []

            return "Execution Flow:\n\n" + "\n".join(steps), []

    log_memory("rag:before_retrieval")
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
    log_memory("rag:after_retrieval")

    if not retrieved_chunks:
        return "No relevant context found in the database. Please try rephrasing your query.", []

    context = build_context(retrieved_chunks)
    unique_files = {
        str(chunk.get("file_name") or "").strip()
        for chunk in retrieved_chunks
        if str(chunk.get("file_name") or "").strip()
    }
    has_multi_file_context = len(unique_files) > 1
    repo_context = repo_indexed or has_multi_file_context
    force_llm = query_type in {"explain", "flow"} or (
        repo_context and _is_broad_or_vague_query(query)
    )

    if force_llm:
        _log_generation_route("LLM")
        log_memory("rag:before_llm_call")
        answer = generate_answer(
            query=query, context=context, chunks=retrieved_chunks)
        return answer, retrieved_chunks

    if query_type == "search":
        _log_generation_route("LOCAL")
        answer = _generate_local_answer(
            query=query, context=context, chunks=retrieved_chunks)
        return answer, retrieved_chunks

    # explain
    _log_generation_route("LLM")
    log_memory("rag:before_llm_call")
    answer = generate_answer(
        query=query, context=context, chunks=retrieved_chunks)
    return answer, retrieved_chunks
