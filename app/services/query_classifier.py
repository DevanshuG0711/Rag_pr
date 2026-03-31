import re


EXPLAIN_TERMS = {"what", "explain", "describe", "meaning"}
SEARCH_TERMS = {"find", "where", "locate"}


def classify_query(query: str) -> str:
    tokens = set(re.findall(r"\b\w+\b", query.lower()))

    if tokens & EXPLAIN_TERMS:
        return "explain"

    if tokens & SEARCH_TERMS:
        return "search"

    return "search"
