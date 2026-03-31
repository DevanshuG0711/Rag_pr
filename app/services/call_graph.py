from __future__ import annotations

from collections import OrderedDict

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser


def _create_parser() -> Parser:
    python_language = Language(tspython.language())

    try:
        return Parser(python_language)
    except TypeError:
        parser = Parser()
        parser.set_language(python_language)
        return parser


def _node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8")


def extract_call_graph(code: str) -> dict[str, list[str]]:
    parser = _create_parser()
    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)

    graph: dict[str, list[str]] = OrderedDict()
    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node is None:
                continue

            func_name = _node_text(name_node, source_bytes)
            called: list[str] = []
            seen_called: set[str] = set()

            body_node = node.child_by_field_name("body")
            if body_node is not None:
                sub_stack = [body_node]
                while sub_stack:
                    sub_node = sub_stack.pop()

                    if sub_node.type == "call":
                        callee = sub_node.child_by_field_name("function")
                        # Keep only simple direct calls like foo(...)
                        if callee is not None and callee.type == "identifier":
                            called_name = _node_text(callee, source_bytes)
                            if called_name in {"print"}:
                                continue
                            if called_name not in seen_called:
                                called.append(called_name)
                                seen_called.add(called_name)

                    # Skip nested defs/classes to keep extraction simple and local.
                    if sub_node.type in {"function_definition", "class_definition"}:
                        continue

                    for child in reversed(sub_node.children):
                        sub_stack.append(child)

            graph[func_name] = called

        for child in reversed(node.children):
            stack.append(child)

    return graph
