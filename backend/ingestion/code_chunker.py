import os

from tree_sitter import Language, Parser

import tree_sitter_c
import tree_sitter_c_sharp
import tree_sitter_cpp
import tree_sitter_go
import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_php
import tree_sitter_python
import tree_sitter_ruby
import tree_sitter_rust
import tree_sitter_typescript


SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    "pycache",
    "dist",
    "build",
    "target",
}

FALLBACK_CHUNK_LINES = 100
FALLBACK_OVERLAP_LINES = 20

LANGUAGE_CONFIG = {
    ".py": {
        "language": "python",
        "grammar": tree_sitter_python.language,
        "symbols": {"class_definition", "function_definition"},
    },
    ".js": {
        "language": "javascript",
        "grammar": tree_sitter_javascript.language,
        "symbols": {"class_declaration", "function_declaration", "method_definition"},
    },
    ".jsx": {
        "language": "javascript",
        "grammar": tree_sitter_javascript.language,
        "symbols": {"class_declaration", "function_declaration", "method_definition"},
    },
    ".ts": {
        "language": "typescript",
        "grammar": tree_sitter_typescript.language_typescript,
        "symbols": {
            "class_declaration",
            "function_declaration",
            "method_definition",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
        },
    },
    ".tsx": {
        "language": "typescript",
        "grammar": tree_sitter_typescript.language_tsx,
        "symbols": {
            "class_declaration",
            "function_declaration",
            "method_definition",
            "interface_declaration",
            "type_alias_declaration",
            "enum_declaration",
        },
    },
    ".java": {
        "language": "java",
        "grammar": tree_sitter_java.language,
        "symbols": {
            "class_declaration",
            "method_declaration",
            "interface_declaration",
            "enum_declaration",
        },
    },
    ".go": {
        "language": "go",
        "grammar": tree_sitter_go.language,
        "symbols": {"function_declaration", "method_declaration", "type_declaration"},
    },
    ".rs": {
        "language": "rust",
        "grammar": tree_sitter_rust.language,
        "symbols": {
            "function_item",
            "struct_item",
            "enum_item",
            "trait_item",
            "impl_item",
        },
    },
    ".c": {
        "language": "c",
        "grammar": tree_sitter_c.language,
        "symbols": {"function_definition", "struct_specifier"},
    },
    ".h": {
        "language": "cpp",
        "grammar": tree_sitter_cpp.language,
        "symbols": {"function_definition", "class_specifier", "struct_specifier"},
    },
    ".hpp": {
        "language": "cpp",
        "grammar": tree_sitter_cpp.language,
        "symbols": {"function_definition", "class_specifier", "struct_specifier"},
    },
    ".cc": {
        "language": "cpp",
        "grammar": tree_sitter_cpp.language,
        "symbols": {"function_definition", "class_specifier", "struct_specifier"},
    },
    ".cpp": {
        "language": "cpp",
        "grammar": tree_sitter_cpp.language,
        "symbols": {"function_definition", "class_specifier", "struct_specifier"},
    },
    ".cxx": {
        "language": "cpp",
        "grammar": tree_sitter_cpp.language,
        "symbols": {"function_definition", "class_specifier", "struct_specifier"},
    },
    ".cs": {
        "language": "csharp",
        "grammar": tree_sitter_c_sharp.language,
        "symbols": {"class_declaration", "method_declaration", "interface_declaration"},
    },
    ".php": {
        "language": "php",
        "grammar": tree_sitter_php.language_php,
        "symbols": {"class_declaration", "method_declaration", "function_definition"},
    },
    ".rb": {
        "language": "ruby",
        "grammar": tree_sitter_ruby.language,
        "symbols": {"class", "method"},
    },
}

IDENTIFIER_NODE_TYPES = {
    "identifier",
    "type_identifier",
    "field_identifier",
    "constant",
    "scope_resolution",
    "scoped_type_identifier",
    "qualified_name",
    "name",
}

SYMBOL_TYPE_MAP = {
    "class": "class",
    "class_definition": "class",
    "class_declaration": "class",
    "class_specifier": "class",
    "function_definition": "function",
    "function_declaration": "function",
    "function_item": "function",
    "method": "method",
    "method_definition": "method",
    "method_declaration": "method",
    "interface_declaration": "interface",
    "enum_declaration": "enum",
    "enum_item": "enum",
    "struct_item": "struct",
    "struct_specifier": "struct",
    "trait_item": "trait",
    "impl_item": "impl",
    "type_alias_declaration": "type",
    "type_declaration": "type",
}


def chunk_codebase(repo_path: str) -> list[dict]:
    if not os.path.isdir(repo_path):
        return []

    chunks: list[dict] = []
    repo_root = os.path.abspath(repo_path)

    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [directory for directory in dirs if directory not in SKIP_DIRS]

        for filename in files:
            file_path = os.path.join(root, filename)
            language_config = get_language_config(file_path)
            if not language_config:
                continue
            chunks.extend(chunk_file(file_path, repo_root, language_config))

    return chunks


def get_language_config(file_path: str) -> dict | None:
    _, extension = os.path.splitext(file_path)
    return LANGUAGE_CONFIG.get(extension.lower())


def chunk_file(file_path: str, repo_root: str, language_config: dict) -> list[dict]:
    relative_path = to_relative_path(file_path, repo_root)
    language = language_config["language"]

    try:
        source_bytes = read_file_bytes(file_path)
        semantic_chunks = extract_semantic_chunks(
            source_bytes,
            relative_path,
            language,
            language_config,
        )
        if semantic_chunks:
            return semantic_chunks
    except Exception:
        pass

    return extract_fallback_chunks(file_path, relative_path, language)


def extract_semantic_chunks(
    source_bytes: bytes,
    relative_path: str,
    language: str,
    language_config: dict,
) -> list[dict]:
    parser = Parser(Language(language_config["grammar"]()))
    tree = parser.parse(source_bytes)
    chunks: list[dict] = []

    def visit(node) -> None:
        if node.type in language_config["symbols"]:
            chunks.append(format_code_chunk(node, source_bytes, relative_path, language))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return chunks


def format_code_chunk(node, source_bytes: bytes, relative_path: str, language: str) -> dict:
    symbol_name = get_symbol_name(node, source_bytes)
    symbol_type = SYMBOL_TYPE_MAP.get(node.type, node.type)
    content = decode_source(source_bytes[node.start_byte : node.end_byte])
    return {
        "content": content,
        "metadata": {
            "source": "code",
            "chunk_type": "code",
            "language": language,
            "file_path": relative_path,
            "symbol_name": symbol_name or "unknown",
            "symbol_type": symbol_type,
        },
    }


def extract_fallback_chunks(file_path: str, relative_path: str, language: str) -> list[dict]:
    source_text = decode_source(read_file_bytes(file_path))
    lines = source_text.splitlines(keepends=True)
    if not lines:
        return []

    chunks: list[dict] = []
    step = FALLBACK_CHUNK_LINES - FALLBACK_OVERLAP_LINES

    for start in range(0, len(lines), step):
        end = min(start + FALLBACK_CHUNK_LINES, len(lines))
        content = "".join(lines[start:end]).strip()
        if content:
            chunks.append(
                {
                    "content": content,
                    "metadata": {
                        "source": "code",
                        "chunk_type": "code",
                        "language": language,
                        "file_path": relative_path,
                        "symbol_name": f"lines_{start + 1}_{end}",
                        "symbol_type": "fixed_size",
                        "start_line": start + 1,
                        "end_line": end,
                    },
                }
            )

        if end == len(lines):
            break

    return chunks


def get_symbol_name(node, source_bytes: bytes) -> str | None:
    name_node = node.child_by_field_name("name")
    if name_node:
        return decode_source(
            source_bytes[name_node.start_byte : name_node.end_byte]
        ).strip()

    identifier_nodes = []
    collect_identifier_nodes(node, identifier_nodes)
    if not identifier_nodes:
        return None

    selected = identifier_nodes[-1] if is_function_like(node.type) else identifier_nodes[0]
    return decode_source(source_bytes[selected.start_byte : selected.end_byte]).strip()


def collect_identifier_nodes(node, matches: list) -> None:
    if node.type in IDENTIFIER_NODE_TYPES:
        matches.append(node)
        return

    for child in node.children:
        collect_identifier_nodes(child, matches)


def is_function_like(node_type: str) -> bool:
    return node_type in {
        "function_definition",
        "function_declaration",
        "function_item",
        "method",
        "method_definition",
        "method_declaration",
    }


def to_relative_path(file_path: str, repo_root: str) -> str:
    return os.path.relpath(file_path, repo_root).replace(os.sep, "/")


def read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as file:
        return file.read()


def decode_source(source_bytes: bytes) -> str:
    return source_bytes.decode("utf-8", errors="replace")
