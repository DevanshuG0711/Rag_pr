import os
from typing import Literal

import networkx as nx
import psycopg2


_call_graph_digraph = nx.DiGraph()


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
    name = str(function_name)
    if not _call_graph_digraph.has_node(name):
        return []
    return list(_call_graph_digraph.successors(name))


def get_callers(function_name: str) -> list[str]:
    name = str(function_name)
    if not _call_graph_digraph.has_node(name):
        return []
    return list(_call_graph_digraph.predecessors(name))


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
    valid_inputs = [
        str(name)
        for name in function_names
        if _call_graph_digraph.has_node(str(name))
    ]

    if max_depth <= 0:
        return list(dict.fromkeys(valid_inputs))

    seen: set[str] = set()
    expanded: list[str] = []
    frontier: list[str] = []

    for normalized in valid_inputs:
        if normalized in seen:
            continue
        seen.add(normalized)
        expanded.append(normalized)
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
                expanded.append(normalized_neighbor)
                next_frontier.append(normalized_neighbor)

        if not next_frontier:
            break
        frontier = next_frontier

    return expanded


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
