from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from program_state_ast_cst_extractor import opaque_id
from program_state_symbol_table_extractor import _call_name


@dataclass(frozen=True)
class CallGraphExtraction:
    language_family: str
    source_hash: str
    call_nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"language_family": self.language_family, "source_hash": self.source_hash, "call_nodes": self.call_nodes, "edges": self.edges, "failures": self.failures}


def _span(node: ast.AST) -> dict[str, int | None]:
    return {"lineno": getattr(node, "lineno", None), "col_offset": getattr(node, "col_offset", None), "end_lineno": getattr(node, "end_lineno", None), "end_col_offset": getattr(node, "end_col_offset", None)}


class CallGraphVisitor(ast.NodeVisitor):
    def __init__(self, *, row_id: str, path: str) -> None:
        self.row_id = row_id
        self.path = path
        self.scope: list[str] = ["<module>"]
        self.call_nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def _scope_name(self) -> str:
        return "::".join(part for part in self.scope if part != "<module>") or "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        callee = _call_name(node.func) or "<unknown>"
        caller = self._scope_name()
        caller_id = opaque_id(self.row_id, self.path, "caller", caller, prefix="call")
        callee_id = opaque_id(self.row_id, self.path, "callee", callee, prefix="call")
        callsite_id = opaque_id(self.row_id, self.path, "callsite", caller, callee, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), prefix="call")
        self.call_nodes.extend([
            {"call_node_id": caller_id, "node_kind": "caller_scope", "name": caller},
            {"call_node_id": callee_id, "node_kind": "callee_reference", "name": callee},
            {"call_node_id": callsite_id, "node_kind": "callsite", "name": callee, "caller": caller, "span": _span(node), "arg_count": len(node.args), "keyword_count": len(node.keywords)},
        ])
        self.edges.append({"src": caller_id, "dst": callsite_id, "edge_type": "contains_callsite"})
        self.edges.append({"src": callsite_id, "dst": callee_id, "edge_type": "calls_reference"})
        self.generic_visit(node)


def extract_python_call_graph(source: str, *, row_id: str = "row", path: str = "memory.py") -> CallGraphExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return CallGraphExtraction("python", source_hash, [], [], [f"syntax_error:{exc.lineno}:{exc.offset}"])
    visitor = CallGraphVisitor(row_id=row_id, path=path)
    visitor.visit(tree)
    dedup: dict[str, dict[str, Any]] = {node["call_node_id"]: node for node in visitor.call_nodes}
    return CallGraphExtraction("python", source_hash, list(dedup.values()), visitor.edges, [])


def extract_call_graph_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {"language_family": language, "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(), "call_nodes": [], "edges": [], "failures": [f"unsupported_language:{language}"]}
    return extract_python_call_graph(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Extract no-authority call graph modality packets from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_call_graph_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
