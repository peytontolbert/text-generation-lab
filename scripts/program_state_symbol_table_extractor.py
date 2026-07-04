from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from program_state_ast_cst_extractor import opaque_id


@dataclass(frozen=True)
class SymbolExtraction:
    language_family: str
    source_hash: str
    symbols: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_family": self.language_family,
            "source_hash": self.source_hash,
            "symbols": self.symbols,
            "edges": self.edges,
            "failures": self.failures,
        }


def _span(node: ast.AST) -> dict[str, int | None]:
    return {
        "lineno": getattr(node, "lineno", None),
        "col_offset": getattr(node, "col_offset", None),
        "end_lineno": getattr(node, "end_lineno", None),
        "end_col_offset": getattr(node, "end_col_offset", None),
    }


def _annotation_text(node: ast.AST | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:
        return type(node).__name__


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args = []
    for arg in list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs):
        args.append({"name": arg.arg, "annotation": _annotation_text(arg.annotation)})
    if node.args.vararg:
        args.append({"name": "*" + node.args.vararg.arg, "annotation": _annotation_text(node.args.vararg.annotation)})
    if node.args.kwarg:
        args.append({"name": "**" + node.args.kwarg.arg, "annotation": _annotation_text(node.args.kwarg.annotation)})
    return {"args": args, "returns": _annotation_text(node.returns)}


class SymbolVisitor(ast.NodeVisitor):
    def __init__(self, *, row_id: str, path: str) -> None:
        self.row_id = row_id
        self.path = path
        self.scope_stack: list[str] = []
        self.symbols: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def _scope_id(self) -> str:
        return "::".join(self.scope_stack) or "<module>"

    def _add_symbol(self, *, kind: str, name: str, node: ast.AST, extra: dict[str, Any] | None = None) -> str:
        symbol_id = opaque_id(self.row_id, self.path, kind, self._scope_id(), name, getattr(node, "lineno", 0), prefix="sym")
        record = {
            "symbol_id": symbol_id,
            "symbol_kind": kind,
            "name": name,
            "qualified_name": "::".join([*self.scope_stack, name]) if self.scope_stack else name,
            "scope": self._scope_id(),
            "span": _span(node),
        }
        if extra:
            record.update(extra)
        self.symbols.append(record)
        return symbol_id

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            symbol_id = self._add_symbol(
                kind="import",
                name=alias.asname or alias.name,
                node=node,
                extra={"module": alias.name, "asname": alias.asname},
            )
            self.edges.append({"src": symbol_id, "dst": opaque_id(alias.name, prefix="dep"), "edge_type": "imports"})
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        module = "." * int(node.level or 0) + (node.module or "")
        for alias in node.names:
            symbol_id = self._add_symbol(
                kind="import",
                name=alias.asname or alias.name,
                node=node,
                extra={"module": module, "imported_name": alias.name, "asname": alias.asname},
            )
            self.edges.append({"src": symbol_id, "dst": opaque_id(module, alias.name, prefix="dep"), "edge_type": "imports"})
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        symbol_id = self._add_symbol(kind="class", name=node.name, node=node, extra={"bases": [_call_name(base) for base in node.bases]})
        if self.scope_stack:
            self.edges.append({"src": opaque_id(self.row_id, self.path, "scope", self._scope_id(), prefix="scope"), "dst": symbol_id, "edge_type": "defines"})
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node, kind="function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node, kind="async_function")

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, kind: str) -> None:
        actual_kind = "method" if self.scope_stack and self.symbols and any(s["symbol_kind"] == "class" and s["qualified_name"] == self._scope_id() for s in self.symbols) else kind
        symbol_id = self._add_symbol(kind=actual_kind, name=node.name, node=node, extra={"signature": _signature(node)})
        if self.scope_stack:
            self.edges.append({"src": opaque_id(self.row_id, self.path, "scope", self._scope_id(), prefix="scope"), "dst": symbol_id, "edge_type": "defines"})
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Call(self, node: ast.Call) -> Any:
        name = _call_name(node.func)
        if name:
            call_id = self._add_symbol(kind="callsite", name=name, node=node, extra={"arg_count": len(node.args), "keyword_count": len(node.keywords)})
            self.edges.append({"src": opaque_id(self.row_id, self.path, "scope", self._scope_id(), prefix="scope"), "dst": call_id, "edge_type": "calls"})
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add_symbol(kind="local", name=target.id, node=target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> Any:
        if isinstance(node.target, ast.Name):
            self._add_symbol(kind="local", name=node.target.id, node=node.target, extra={"annotation": _annotation_text(node.annotation)})
        self.generic_visit(node)


def extract_python_symbols(source: str, *, row_id: str = "row", path: str = "memory.py") -> SymbolExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return SymbolExtraction(
            language_family="python",
            source_hash=source_hash,
            symbols=[],
            edges=[],
            failures=[f"syntax_error:{exc.lineno}:{exc.offset}"],
        )
    visitor = SymbolVisitor(row_id=row_id, path=path)
    visitor.visit(tree)
    return SymbolExtraction("python", source_hash, visitor.symbols, visitor.edges, [])


def extract_symbol_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {
            "language_family": language,
            "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "symbols": [],
            "edges": [],
            "failures": [f"unsupported_language:{language}"],
        }
    return extract_python_symbols(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Extract a no-authority symbol table modality packet from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_symbol_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
