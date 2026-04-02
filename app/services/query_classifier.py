import re


EXPLAIN_TERMS = {"what", "explain", "describe", "meaning"}
SEARCH_TERMS = {"find", "where", "locate"}


def classify_query(query: str) -> str:
    normalized = query.lower().strip()

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
