from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from program_state_ast_cst_extractor import opaque_id
from program_state_symbol_table_extractor import _annotation_text


@dataclass(frozen=True)
class TypeSignatureExtraction:
    language_family: str
    source_hash: str
    signatures: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_family": self.language_family,
            "source_hash": self.source_hash,
            "signatures": self.signatures,
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


def _function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args: list[dict[str, Any]] = []
    ordered = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    for arg in ordered:
        args.append({"name": arg.arg, "annotation": _annotation_text(arg.annotation)})
    if node.args.vararg:
        args.append({"name": "*" + node.args.vararg.arg, "annotation": _annotation_text(node.args.vararg.annotation)})
    if node.args.kwarg:
        args.append({"name": "**" + node.args.kwarg.arg, "annotation": _annotation_text(node.args.kwarg.annotation)})
    return {"args": args, "returns": _annotation_text(node.returns)}


class TypeSignatureVisitor(ast.NodeVisitor):
    def __init__(self, *, row_id: str, path: str) -> None:
        self.row_id = row_id
        self.path = path
        self.scope: list[str] = []
        self.signatures: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def _scope_name(self) -> str:
        return "::".join(self.scope) or "<module>"

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        class_id = opaque_id(self.row_id, self.path, "class_signature", self._scope_name(), node.name, getattr(node, "lineno", 0), prefix="type")
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append(type(base).__name__)
        self.signatures.append({
            "signature_id": class_id,
            "signature_kind": "class",
            "name": node.name,
            "qualified_name": "::".join([*self.scope, node.name]) if self.scope else node.name,
            "bases": bases,
            "span": _span(node),
        })
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        self._visit_function(node, "function")

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        self._visit_function(node, "async_function")

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, kind: str) -> None:
        actual_kind = "method" if self.scope else kind
        sig_id = opaque_id(self.row_id, self.path, "function_signature", self._scope_name(), node.name, getattr(node, "lineno", 0), prefix="type")
        sig = _function_signature(node)
        self.signatures.append({
            "signature_id": sig_id,
            "signature_kind": actual_kind,
            "name": node.name,
            "qualified_name": "::".join([*self.scope, node.name]) if self.scope else node.name,
            "signature": sig,
            "span": _span(node),
        })
        for arg in sig["args"]:
            if arg.get("annotation"):
                ann_id = opaque_id(self.row_id, self.path, "annotation", sig_id, arg["name"], arg["annotation"], prefix="type")
                self.edges.append({"src": sig_id, "dst": ann_id, "edge_type": "arg_has_annotation", "arg": arg["name"], "annotation": arg["annotation"]})
        if sig.get("returns"):
            ret_id = opaque_id(self.row_id, self.path, "returns", sig_id, sig["returns"], prefix="type")
            self.edges.append({"src": sig_id, "dst": ret_id, "edge_type": "returns_annotation", "annotation": sig["returns"]})
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()


def extract_python_type_signatures(source: str, *, row_id: str = "row", path: str = "memory.py") -> TypeSignatureExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return TypeSignatureExtraction("python", source_hash, [], [], [f"syntax_error:{exc.lineno}:{exc.offset}"])
    visitor = TypeSignatureVisitor(row_id=row_id, path=path)
    visitor.visit(tree)
    return TypeSignatureExtraction("python", source_hash, visitor.signatures, visitor.edges, [])


def extract_type_signature_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {"language_family": language, "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(), "signatures": [], "edges": [], "failures": [f"unsupported_language:{language}"]}
    return extract_python_type_signatures(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="Extract no-authority type/signature modality packets from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_type_signature_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
