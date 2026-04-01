from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Dict, List, TypedDict

import tree_sitter_python as tspython
from tree_sitter import Language, Node, Parser


class ASTChunk(TypedDict):
    chunk_text: str
    name: str
    type: str
    start_line: int
    end_line: int
    file_name: str
    docstring: str
    imports: list[str]


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


def _node_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8")


def _extract_file_imports(root_node: Node, source_bytes: bytes) -> list[str]:
    imports: list[str] = []

    for child in root_node.children:
        if child.type in {"import_statement", "import_from_statement"}:
            statement = _node_text(child, source_bytes).strip()
            if statement:
                imports.append(statement)

    return imports


def _extract_function_docstring(function_node: Node, source_bytes: bytes) -> str | None:
    body_node = function_node.child_by_field_name("body")
    if body_node is None:
        return None

    first_named = None
    for child in body_node.children:
        if child.is_named:
            first_named = child
            break

    if first_named is None or first_named.type != "expression_statement":
        return None

    string_node = None
    for child in first_named.children:
        if child.is_named:
            string_node = child
            break

    if string_node is None or string_node.type not in {"string", "concatenated_string"}:
        return None

    raw_literal = _node_text(string_node, source_bytes)
    try:
        value = ast.literal_eval(raw_literal)
        return value if isinstance(value, str) else None
    except Exception:
        return raw_literal.strip()


def _extract_chunk(node: Node, source_bytes: bytes, file_name: str) -> ASTChunk:
    node_type = "function" if node.type == "function_definition" else "class"

    return {
        "chunk_text": _node_text(node, source_bytes),
        "name": _node_name(node, source_bytes),
        "type": node_type,
        "start_line": node.start_point[0] + 1,
        "end_line": node.end_point[0] + 1,
        "file_name": file_name,
    }


def extract_ast_chunks(code: str, parser) -> List[Dict]:
    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)
    imports = _extract_file_imports(tree.root_node, source_bytes)

    chunks: List[Dict] = []
    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        if node.type in {"function_definition", "class_definition"}:
            name_node = node.child_by_field_name("name")
            symbol_name = _node_name(node, source_bytes) if name_node is not None else "<anonymous>"

            chunk: Dict[str, object] = {
                "chunk_text": _node_text(node, source_bytes),
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "imports": imports,
            }

            if node.type == "function_definition":
                chunk["function_name"] = symbol_name
                docstring = _extract_function_docstring(node, source_bytes)
                if docstring:
                    chunk["docstring"] = docstring
            else:
                chunk["class_name"] = symbol_name

            chunks.append(chunk)
            # Do not descend into this node to avoid nested duplication.
            continue

        for child in reversed(node.children):
            stack.append(child)

    return chunks


def extract_python_ast_chunks(file_path: str, file_content: str) -> list[ASTChunk]:
    parser = _create_parser()
    file_name = Path(file_path).name
    raw_chunks = extract_ast_chunks(code=file_content, parser=parser)

    chunks: list[ASTChunk] = []
    for raw in raw_chunks:
        function_name = raw.get("function_name")
        class_name = raw.get("class_name")

        if function_name is not None:
            name = str(function_name)
            node_type = "function"
        else:
            name = str(class_name)
            node_type = "class"

        chunks.append(
            {
                "chunk_text": str(raw.get("chunk_text") or ""),
                "name": name,
                "type": node_type,
                "start_line": int(raw["start_line"]),
                "end_line": int(raw["end_line"]),
                "file_name": file_name,
                "docstring": str(raw.get("docstring") or ""),
                "imports": list(raw.get("imports") or []),
            }
        )

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
