from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from program_state_ast_cst_extractor import opaque_id
from program_state_symbol_table_extractor import _call_name


@dataclass(frozen=True)
class DataControlFlowExtraction:
    language_family: str
    source_hash: str
    data_nodes: list[dict[str, Any]]
    control_nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_family": self.language_family,
            "source_hash": self.source_hash,
            "data_nodes": self.data_nodes,
            "control_nodes": self.control_nodes,
            "edges": self.edges,
            "failures": self.failures,
        }


def _span(node: ast.AST) -> dict[str, int | None]:
    return {"lineno": getattr(node, "lineno", None), "col_offset": getattr(node, "col_offset", None), "end_lineno": getattr(node, "end_lineno", None), "end_col_offset": getattr(node, "end_col_offset", None)}


def _target_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for elt in node.elts:
            names.extend(_target_names(elt))
        return names
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return [f"{base}.{node.attr}" if base else node.attr]
    return []


def _load_names(node: ast.AST) -> list[str]:
    names: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            names.append(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
            call_name = _call_name(child)
            if call_name:
                names.append(call_name)
    return sorted(set(names))


class DataControlVisitor(ast.NodeVisitor):
    def __init__(self, *, row_id: str, path: str) -> None:
        self.row_id = row_id
        self.path = path
        self.scope: list[str] = ["<module>"]
        self.data_nodes: list[dict[str, Any]] = []
        self.control_nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._previous_stmt_by_scope: dict[str, str] = {}

    def _scope_name(self) -> str:
        return "::".join(part for part in self.scope if part != "<module>") or "<module>"

    def _stmt_id(self, node: ast.AST, kind: str) -> str:
        return opaque_id(self.row_id, self.path, "control", self._scope_name(), kind, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), prefix="flow")

    def _add_control(self, node: ast.AST, kind: str, extra: dict[str, Any] | None = None) -> str:
        node_id = self._stmt_id(node, kind)
        record = {"control_node_id": node_id, "control_kind": kind, "scope": self._scope_name(), "span": _span(node)}
        if extra:
            record.update(extra)
        self.control_nodes.append(record)
        prev = self._previous_stmt_by_scope.get(self._scope_name())
        if prev and prev != node_id:
            self.edges.append({"src": prev, "dst": node_id, "edge_type": "control_next"})
        self._previous_stmt_by_scope[self._scope_name()] = node_id
        return node_id

    def _add_data_node(self, name: str, kind: str, node: ast.AST, extra: dict[str, Any] | None = None) -> str:
        node_id = opaque_id(self.row_id, self.path, "data", self._scope_name(), kind, name, getattr(node, "lineno", 0), getattr(node, "col_offset", 0), prefix="data")
        record = {"data_node_id": node_id, "data_kind": kind, "name": name, "scope": self._scope_name(), "span": _span(node)}
        if extra:
            record.update(extra)
        self.data_nodes.append(record)
        return node_id

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        ctrl = self._add_control(node, "function_entry", {"name": node.name})
        self.scope.append(node.name)
        old_prev = self._previous_stmt_by_scope.get(self._scope_name())
        self._previous_stmt_by_scope[self._scope_name()] = ctrl
        for arg in node.args.args:
            data_id = self._add_data_node(arg.arg, "argument", arg, {})
            self.edges.append({"src": data_id, "dst": ctrl, "edge_type": "argument_enters_scope"})
        self.generic_visit(node)
        if old_prev is None:
            self._previous_stmt_by_scope.pop(self._scope_name(), None)
        else:
            self._previous_stmt_by_scope[self._scope_name()] = old_prev
        self.scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self.visit_FunctionDef(node)  # same static control surface for this extractor

    def visit_Assign(self, node: ast.Assign) -> Any:
        ctrl = self._add_control(node, "assign")
        sources = _load_names(node.value)
        for target in node.targets:
            for name in _target_names(target):
                target_id = self._add_data_node(name, "definition", target, {"sources": sources})
                self.edges.append({"src": ctrl, "dst": target_id, "edge_type": "defines_value"})
                for source in sources:
                    source_id = self._add_data_node(source, "use", node.value, {})
                    self.edges.append({"src": source_id, "dst": target_id, "edge_type": "data_depends_on"})
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        ctrl = self._add_control(node, "ann_assign")
        sources = _load_names(node.value) if node.value else []
        for name in _target_names(node.target):
            target_id = self._add_data_node(name, "definition", node.target, {"sources": sources})
            self.edges.append({"src": ctrl, "dst": target_id, "edge_type": "defines_value"})
            for source in sources:
                source_id = self._add_data_node(source, "use", node.value or node.target, {})
                self.edges.append({"src": source_id, "dst": target_id, "edge_type": "data_depends_on"})
        self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> Any:
        ctrl = self._add_control(node, "return")
        for source in _load_names(node.value) if node.value else []:
            source_id = self._add_data_node(source, "return_use", node, {})
            self.edges.append({"src": source_id, "dst": ctrl, "edge_type": "return_depends_on"})
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> Any:
        ctrl = self._add_control(node, "if", {"test_sources": _load_names(node.test)})
        for source in _load_names(node.test):
            source_id = self._add_data_node(source, "condition_use", node.test, {})
            self.edges.append({"src": source_id, "dst": ctrl, "edge_type": "condition_depends_on"})
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        ctrl = self._add_control(node, "for", {"iter_sources": _load_names(node.iter)})
        for name in _target_names(node.target):
            target_id = self._add_data_node(name, "loop_target", node.target, {})
            self.edges.append({"src": ctrl, "dst": target_id, "edge_type": "defines_loop_target"})
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:
        ctrl = self._add_control(node, "while", {"test_sources": _load_names(node.test)})
        for source in _load_names(node.test):
            source_id = self._add_data_node(source, "condition_use", node.test, {})
            self.edges.append({"src": source_id, "dst": ctrl, "edge_type": "condition_depends_on"})
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:
        self._add_control(node, "try")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node.func)
        if name:
            ctrl = self._add_control(node, "call", {"callee": name})
            for source in _load_names(node):
                source_id = self._add_data_node(source, "call_use", node, {})
                self.edges.append({"src": source_id, "dst": ctrl, "edge_type": "call_depends_on"})
        self.generic_visit(node)


def extract_python_data_control_flow(source: str, *, row_id: str = "row", path: str = "memory.py") -> DataControlFlowExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return DataControlFlowExtraction("python", source_hash, [], [], [], [f"syntax_error:{exc.lineno}:{exc.offset}"])
    visitor = DataControlVisitor(row_id=row_id, path=path)
    visitor.visit(tree)
    data = {node["data_node_id"]: node for node in visitor.data_nodes}
    control = {node["control_node_id"]: node for node in visitor.control_nodes}
    return DataControlFlowExtraction("python", source_hash, list(data.values()), list(control.values()), visitor.edges, [])


def extract_data_control_flow_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {"language_family": language, "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(), "data_nodes": [], "control_nodes": [], "edges": [], "failures": [f"unsupported_language:{language}"]}
    return extract_python_data_control_flow(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Extract no-authority data-flow/control-flow modality packets from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_data_control_flow_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
