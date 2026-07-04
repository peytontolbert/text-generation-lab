from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any


def opaque_id(*parts: object, prefix: str = "n") -> str:
    payload = "::".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


@dataclass(frozen=True)
class AstExtraction:
    language_family: str
    source_hash: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_family": self.language_family,
            "source_hash": self.source_hash,
            "nodes": self.nodes,
            "edges": self.edges,
            "failures": self.failures,
        }


def _node_span(node: ast.AST) -> dict[str, int | None]:
    return {
        "lineno": getattr(node, "lineno", None),
        "col_offset": getattr(node, "col_offset", None),
        "end_lineno": getattr(node, "end_lineno", None),
        "end_col_offset": getattr(node, "end_col_offset", None),
    }


def _safe_label(node: ast.AST) -> str | None:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.arg):
        return node.arg
    if isinstance(node, ast.alias):
        return node.asname or node.name
    return None


def extract_python_ast(source: str, *, row_id: str = "row", path: str = "memory.py") -> AstExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return AstExtraction(
            language_family="python",
            source_hash=source_hash,
            nodes=[],
            edges=[],
            failures=[f"syntax_error:{exc.lineno}:{exc.offset}"],
        )

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def visit(node: ast.AST, parent_id: str | None, field_name: str | None, index: int) -> str:
        node_id = opaque_id(row_id, path, type(node).__name__, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), field_name, index)
        record = {
            "node_id": node_id,
            "modality": "cst_ast",
            "node_type": type(node).__name__,
            "span": _node_span(node),
            "label": _safe_label(node),
        }
        nodes.append(record)
        if parent_id is not None:
            edges.append({
                "src": parent_id,
                "dst": node_id,
                "edge_type": "ast_child",
                "field": field_name,
                "index": index,
            })
        for child_index, child in enumerate(ast.iter_child_nodes(node)):
            visit(child, node_id, None, child_index)
        return node_id

    root_id = visit(tree, None, "root", 0)
    nodes.insert(0, {
        "node_id": opaque_id(row_id, path, "file", prefix="file"),
        "modality": "source_text",
        "node_type": "file",
        "span": {"lineno": 1, "col_offset": 0, "end_lineno": len(source.splitlines()), "end_col_offset": None},
        "label": path,
        "root_ast_node_id": root_id,
    })
    edges.insert(0, {
        "src": nodes[0]["node_id"],
        "dst": root_id,
        "edge_type": "contains_ast_root",
        "field": "body",
        "index": 0,
    })
    return AstExtraction(language_family="python", source_hash=source_hash, nodes=nodes, edges=edges, failures=[])


def extract_ast_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {
            "language_family": language,
            "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "nodes": [],
            "edges": [],
            "failures": [f"unsupported_language:{language}"],
        }
    return extract_python_ast(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Extract a no-authority AST/CST modality packet from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_ast_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
