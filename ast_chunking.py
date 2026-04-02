from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import TypedDict

import tree_sitter_go as tsgo
import tree_sitter_javascript as tsjavascript
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
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


LANGUAGE_BY_EXTENSION: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
}


TARGET_NODE_TYPES: dict[str, dict[str, str]] = {
    "python": {
        "function_definition": "function",
        "class_definition": "class",
    },
    "javascript": {
        "function_declaration": "function",
        "method_definition": "function",
        "class_declaration": "class",
    },
    "typescript": {
        "function_declaration": "function",
        "method_definition": "function",
        "class_declaration": "class",
    },
    "go": {
        "function_declaration": "function",
        "method_declaration": "function",
        "type_declaration": "class",
    },
}


def _detect_language(file_path: str) -> str | None:
    extension = Path(file_path).suffix.lower()
    return LANGUAGE_BY_EXTENSION.get(extension)


def _create_parser(language_name: str) -> Parser:
    if language_name == "python":
        language = Language(tspython.language())
    elif language_name == "javascript":
        language = Language(tsjavascript.language())
    elif language_name == "typescript":
        language = Language(tstypescript.language_typescript())
    elif language_name == "go":
        language = Language(tsgo.language())
    else:
        raise ValueError(f"Unsupported language: {language_name}")

    # Support both newer and older tree-sitter Parser constructors.
    try:
        return Parser(language)
    except TypeError:
        parser = Parser()
        parser.set_language(language)
        return parser


def _node_name(node: Node, source_bytes: bytes) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return "<anonymous>"
    return source_bytes[name_node.start_byte : name_node.end_byte].decode("utf-8")


def _node_text(node: Node, source_bytes: bytes) -> str:
    # Use exact byte boundaries from tree-sitter for stable chunk extraction.
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8")


def _extract_file_imports(root_node: Node, source_bytes: bytes, language_name: str) -> list[str]:
    imports: list[str] = []

    if language_name == "python":
        import_types = {"import_statement", "import_from_statement"}
    elif language_name in {"javascript", "typescript"}:
        import_types = {"import_statement"}
    elif language_name == "go":
        import_types = {"import_declaration"}
    else:
        return imports

    for child in root_node.children:
        if child.type in import_types:
            statement = _node_text(child, source_bytes).strip()
            if statement:
                imports.append(statement)

    return imports


def _extract_python_function_docstring(node: Node, source_bytes: bytes, language_name: str) -> str:
    if language_name != "python" or node.type != "function_definition":
        return ""

    body_node = node.child_by_field_name("body")
    if body_node is None:
        return ""

    first_named = None
    for child in body_node.children:
        if child.is_named:
            first_named = child
            break

    if first_named is None or first_named.type != "expression_statement":
        return ""

    string_node = None
    for child in first_named.children:
        if child.is_named:
            string_node = child
            break

    if string_node is None or string_node.type not in {"string", "concatenated_string"}:
        return ""

    raw_literal = _node_text(string_node, source_bytes)
    try:
        value = ast.literal_eval(raw_literal)
        return value if isinstance(value, str) else ""
    except Exception:
        return raw_literal.strip()


def extract_ast_chunks(code: str, parser: Parser, language_name: str, file_name: str) -> list[ASTChunk]:
    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)
    target_types = TARGET_NODE_TYPES.get(language_name)
    if not target_types:
        return []
    file_imports = _extract_file_imports(tree.root_node, source_bytes, language_name)

    chunks: list[ASTChunk] = []
    stack = [tree.root_node]

    while stack:
        node = stack.pop()

        if node.type in target_types:
            docstring = _extract_python_function_docstring(node, source_bytes, language_name)
            chunks.append(
                {
                    "name": _node_name(node, source_bytes),
                    "type": target_types[node.type],
                    "file_name": file_name,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "chunk_text": _node_text(node, source_bytes),
                    "docstring": docstring,
                    "imports": file_imports,
                }
            )
            # Do not descend into this node to avoid nested duplication.
            continue

        for child in reversed(node.children):
            stack.append(child)

    return chunks


def extract_code_ast_chunks(file_path: str, file_content: str) -> list[ASTChunk]:
    language_name = _detect_language(file_path)
    if language_name is None:
        return []

    parser = _create_parser(language_name=language_name)
    file_name = Path(file_path).name
    return extract_ast_chunks(
        code=file_content,
        parser=parser,
        language_name=language_name,
        file_name=file_name,
    )


def extract_python_ast_chunks(file_path: str, file_content: str) -> list[ASTChunk]:
    return extract_code_ast_chunks(file_path=file_path, file_content=file_content)


def _main() -> None:
    cli = argparse.ArgumentParser(description="Extract function/class chunks from a code file")
    cli.add_argument("file_path", help="Path to a .py/.js/.ts/.go file")
    args = cli.parse_args()

    path = Path(args.file_path)
    content = path.read_text(encoding="utf-8")
    chunks = extract_code_ast_chunks(file_path=str(path), file_content=content)
    print(json.dumps(chunks, indent=2))


if __name__ == "__main__":
    _main()
