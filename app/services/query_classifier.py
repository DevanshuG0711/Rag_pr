import os
import re
import json
import logging
from urllib import request as urllib_request
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv

load_dotenv()

from app.services.tls_http import format_tls_error


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
VALID_LABELS = {"explain", "find_usage", "flow", "search"}
logger = logging.getLogger(__name__)


def _normalize_label(raw_label: str) -> str:
    normalized = str(raw_label or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    normalized = re.sub(r"[^a-z_]", "", normalized)

    alias_map = {
        "findusage": "find_usage",
        "find_use": "find_usage",
        "usage": "find_usage",
    }
    normalized = alias_map.get(normalized, normalized)
    return normalized


def _normalize_query_typos(query: str) -> str:
    normalized = query.lower().strip()
    typo_map = {
        "cal": "call",
        "cals": "calls",
        "clls": "calls",
        "clal": "call",
        "fucntion": "function",
        "funtion": "function",
    }
    for typo, fixed in typo_map.items():
        normalized = re.sub(rf"\b{re.escape(typo)}\b", fixed, normalized)
    return normalized


def classify_query_rule_based(query: str) -> str:
    normalized = _normalize_query_typos(query)

    # Priority 1: find_usage
    if re.search(r"\b(who\s+calls|which\s+function\s+calls)\b", normalized):
        return "find_usage"
    if re.search(r"\bcall(?:s|ed|ing)?\b", normalized):
        return "find_usage"

    # Priority 2: flow
    if re.search(r"\b(flow|dependency)\b", normalized):
        return "flow"

    # Priority 3: explain
    if re.search(r"\b(what|explain|describe)\b", normalized):
        return "explain"

    # Priority 4: default
    return "search"


def classify_query_llm(query: str) -> str:
    api_key = str(os.getenv("GROQ_API_KEY", "")).strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")

    prompt = (
        "You are an intent classifier for a code assistant.\n"
        "Classify the user query into exactly one label from this set:\n"
        "explain, find_usage, flow, search\n\n"
        "Rules:\n"
        "- Return ONLY the label text, nothing else.\n"
        "- Handle typos and natural language.\n"
        "- find_usage: asking who calls what / usage of a function.\n"
        "- flow: asking for call flow/dependency path/sequence.\n"
        "- explain: asking to explain meaning/behavior.\n"
        "- search: general lookup/retrieval.\n\n"
        "Examples:\n"
        "- who cals login -> find_usage\n"
        "- show dependency flow for auth -> flow\n"
        "- explain validate_user -> explain\n"
        "- find login file -> search\n\n"
        f"User query: {query}\n"
    )

    model_name = str(os.getenv("GROQ_MODEL", GROQ_MODEL)).strip() or GROQ_MODEL
    print("GROQ MODEL:", model_name)
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are an intent classifier. Return only one label.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib_request.Request(
        GROQ_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "python-requests/2.31.0",
        },
        method="POST",
    )

    with urllib_request.urlopen(req, timeout=10.0) as response:
        if response.status != 200:
            raise ValueError(f"Groq returned status {response.status}")

        body = response.read().decode("utf-8")
        parsed = json.loads(body)
        label = _normalize_label(
            str(
                (
                    parsed.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                )
            )
        )

        if label not in VALID_LABELS:
            raise ValueError(f"Invalid label from LLM: {label}")

        return label


def classify_query(query: str) -> str:
    try:
        return classify_query_llm(query)
    except (URLError, HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("Query classification fallback (Groq unavailable): %s", format_tls_error(exc))
        return classify_query_rule_based(query)
