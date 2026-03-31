from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser


class ASTChunk(TypedDict):
    chunk_text: str
    name: str
    type: str
    start_line: int
    end_line: int
    file_name: str


def _create_parser() -> Parser:
    python_language = Language(tspython.language())

    # Support both newer and older tree-sitter Parser constructors.
    try:
        return Parser(python_language)
    except TypeError:
        parser = Parser()
        parser.set_language(python_language)
        return parser


def _node_name(node: Node, source_bytes: bytes) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return "<anonymous>"
    return source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")


def _extract_chunk(node: Node, source_bytes: bytes, file_name: str) -> ASTChunk:
    node_type = "function" if node.type == "function_definition" else "class"

    return {
        "chunk_text": source_bytes[node.start_byte : node.end_byte].decode("utf-8"),
        "name": _node_name(node, source_bytes),
        "type": node_type,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "file_name": file_name,
    }


def extract_python_ast_chunks(file_path: str, file_content: str) -> list[ASTChunk]:
    parser = _create_parser()
    source_bytes = file_content.encode("utf-8")
    tree = parser.parse(source_bytes)

    file_name = Path(file_path).name
    chunks: list[ASTChunk] = []
    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        if node.type in {"function_definition", "class_definition"}:
            chunks.append(_extract_chunk(node, source_bytes, file_name))

        for child in reversed(node.children):
            stack.append(child)

    return chunks


def _main() -> None:
    cli = argparse.ArgumentParser(description="Extract function/class chunks from a Python file")
    cli.add_argument("file_path", help="Path to a Python file")
    args = cli.parse_args()

    path = Path(args.file_path)
    content = path.read_text(encoding="utf-8")
    chunks = extract_python_ast_chunks(file_path=str(path), file_content=content)
    print(json.dumps(chunks, indent=2))


if __name__ == "__main__":
    _main()
