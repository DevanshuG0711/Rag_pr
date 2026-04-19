import os
from typing import Literal

import networkx as nx
import psycopg2


_call_graph_digraph = nx.DiGraph()


def _qualified_name(file_name: str, function_name: str) -> str:
    return f"{file_name}::{function_name}"


def _base_function_name(node_name: str) -> str:
    if "::" in node_name:
        return node_name.split("::", 1)[1]
    return node_name


def _matching_nodes(function_name: str) -> list[str]:
    name = str(function_name)
    if _call_graph_digraph.has_node(name):
        return [name]

    suffix = f"::{name}"
    return [
        str(node)
        for node in _call_graph_digraph.nodes
        if str(node).endswith(suffix)
    ]


def build_graph(call_graph: dict[str, list[str]]) -> nx.DiGraph:
    graph = nx.DiGraph()

    for function_name, called_functions in (call_graph or {}).items():
        caller = str(function_name)
        graph.add_node(caller)

        for callee in called_functions or []:
            callee_name = str(callee)
            graph.add_node(callee_name)
            graph.add_edge(caller, callee_name)

    global _call_graph_digraph
    _call_graph_digraph = graph
    return graph


def get_callees(function_name: str) -> list[str]:
    matched_nodes = _matching_nodes(function_name)
    if not matched_nodes:
        return []

    callees: list[str] = []
    seen: set[str] = set()
    for node in matched_nodes:
        for callee in _call_graph_digraph.successors(node):
            base = _base_function_name(str(callee))
            if base in seen:
                continue
            seen.add(base)
            callees.append(base)

    return callees


def get_callers(function_name: str) -> list[str]:
    matched_nodes = _matching_nodes(function_name)
    if not matched_nodes:
        return []

    callers: list[str] = []
    seen: set[str] = set()
    for node in matched_nodes:
        for caller in _call_graph_digraph.predecessors(node):
            base = _base_function_name(str(caller))
            if base in seen:
                continue
            seen.add(base)
            callers.append(base)

    return callers


def expand_with_graph(function_names: list[str], max_depth: int = 1) -> list[str]:
    return expand_with_graph_mode(
        function_names=function_names,
        max_depth=max_depth,
        mode="both",
    )


def expand_with_graph_mode(
    function_names: list[str],
    max_depth: int = 1,
    mode: Literal["callers", "callees", "both"] = "both",
) -> list[str]:
    valid_inputs: list[str] = []
    for name in function_names:
        valid_inputs.extend(_matching_nodes(str(name)))
    valid_inputs = list(dict.fromkeys(valid_inputs))

    if max_depth <= 0:
        return list(dict.fromkeys(valid_inputs))

    seen: set[str] = set()
    expanded_nodes: list[str] = []
    frontier: list[str] = []

    for normalized in valid_inputs:
        if normalized in seen:
            continue
        seen.add(normalized)
        expanded_nodes.append(normalized)
        frontier.append(normalized)

    for _ in range(max_depth):
        next_frontier: list[str] = []

        for fn_name in frontier:
            neighbors: list[str] = []
            if _call_graph_digraph.has_node(fn_name):
                if mode in {"callees", "both"}:
                    neighbors.extend(_call_graph_digraph.successors(fn_name))
                if mode in {"callers", "both"}:
                    neighbors.extend(_call_graph_digraph.predecessors(fn_name))

            for neighbor in neighbors:
                normalized_neighbor = str(neighbor)
                if normalized_neighbor in seen:
                    continue
                seen.add(normalized_neighbor)
                expanded_nodes.append(normalized_neighbor)
                next_frontier.append(normalized_neighbor)

        if not next_frontier:
            break
        frontier = next_frontier

    expanded_functions: list[str] = []
    seen_functions: set[str] = set()
    for node in expanded_nodes:
        base = _base_function_name(node)
        if base in seen_functions:
            continue
        seen_functions.add(base)
        expanded_functions.append(base)

    return expanded_functions


def get_call_graph_for_file(file_name: str) -> dict[str, list[str]]:
    if not file_name:
        return {}

    dsn = os.getenv("POSTGRES_DSN") or ""
    if not dsn:
        return {}

    graph: dict[str, list[str]] = {}

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT function_name, called_functions
                FROM call_graph
                WHERE file_name = %s
                """,
                (file_name,),
            )
            rows = cur.fetchall()

    for function_name, called_functions in rows:
        graph[str(function_name)] = [str(name) for name in (called_functions or [])]

    return graph


def get_all_call_graph() -> dict[str, list[str]]:
    dsn = os.getenv("POSTGRES_DSN") or ""
    if not dsn:
        return {}

    graph: dict[str, list[str]] = {}

    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT file_name, function_name, called_functions
                FROM call_graph
                """
            )
            rows = cur.fetchall()

    qualified_by_file_and_function: dict[tuple[str, str], str] = {}
    qualified_by_function: dict[str, list[str]] = {}
    normalized_rows: list[tuple[str, str, list[str]]] = []

    for file_name, function_name, called_functions in rows:
        normalized_file = str(file_name)
        normalized_function = str(function_name)
        qualified = _qualified_name(normalized_file, normalized_function)
        qualified_by_file_and_function[(normalized_file, normalized_function)] = qualified
        qualified_by_function.setdefault(normalized_function, []).append(qualified)
        normalized_rows.append(
            (
                normalized_file,
                normalized_function,
                [str(name) for name in (called_functions or [])],
            )
        )

    for file_name, function_name, called_functions in normalized_rows:
        key = qualified_by_file_and_function[(file_name, function_name)]
        existing = graph.get(key, [])

        for callee_name in called_functions:
            same_file_key = (file_name, callee_name)
            if same_file_key in qualified_by_file_and_function:
                candidate_targets = [qualified_by_file_and_function[same_file_key]]
            else:
                candidate_targets = qualified_by_function.get(callee_name, [])

            if not candidate_targets:
                candidate_targets = [callee_name]

            for target in candidate_targets:
                if target not in existing:
                    existing.append(target)

        graph[key] = existing

    return graph
