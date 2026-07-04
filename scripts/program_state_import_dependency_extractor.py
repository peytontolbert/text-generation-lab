from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from program_state_ast_cst_extractor import opaque_id


@dataclass(frozen=True)
class ImportDependencyExtraction:
    language_family: str
    source_hash: str
    dependencies: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    failures: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language_family": self.language_family,
            "source_hash": self.source_hash,
            "dependencies": self.dependencies,
            "edges": self.edges,
            "failures": self.failures,
        }


def _top_package(module: str) -> str:
    stripped = module.lstrip(".")
    if not stripped:
        return module
    return stripped.split(".", 1)[0]


class ImportDependencyVisitor(ast.NodeVisitor):
    def __init__(self, *, row_id: str, path: str) -> None:
        self.row_id = row_id
        self.path = path
        self.dependencies: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def _add_dep(self, *, module: str, imported_name: str | None, asname: str | None, lineno: int | None, relative: bool) -> str:
        package = _top_package(module or imported_name or "")
        dep_id = opaque_id(self.row_id, self.path, module, imported_name, asname, lineno, prefix="dep")
        self.dependencies.append({
            "dependency_id": dep_id,
            "module": module,
            "package": package,
            "imported_name": imported_name,
            "asname": asname,
            "relative": relative,
            "lineno": lineno,
        })
        self.edges.append({
            "src": opaque_id(self.row_id, self.path, prefix="file"),
            "dst": dep_id,
            "edge_type": "imports",
        })
        return dep_id

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            self._add_dep(module=alias.name, imported_name=None, asname=alias.asname, lineno=getattr(node, "lineno", None), relative=False)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        module = "." * int(node.level or 0) + (node.module or "")
        for alias in node.names:
            self._add_dep(
                module=module,
                imported_name=alias.name,
                asname=alias.asname,
                lineno=getattr(node, "lineno", None),
                relative=bool(node.level),
            )


def extract_python_import_dependencies(source: str, *, row_id: str = "row", path: str = "memory.py") -> ImportDependencyExtraction:
    source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return ImportDependencyExtraction(
            language_family="python",
            source_hash=source_hash,
            dependencies=[],
            edges=[],
            failures=[f"syntax_error:{exc.lineno}:{exc.offset}"],
        )
    visitor = ImportDependencyVisitor(row_id=row_id, path=path)
    visitor.visit(tree)
    return ImportDependencyExtraction("python", source_hash, visitor.dependencies, visitor.edges, [])


def extract_import_dependency_packet(row: dict[str, Any]) -> dict[str, Any]:
    language = str(row.get("language_family") or row.get("language") or "python")
    source = str(row.get("source_text") or row.get("code") or "")
    row_id = str(row.get("row_id") or "row")
    path = str(row.get("path") or "memory.py")
    if language != "python":
        return {
            "language_family": language,
            "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "dependencies": [],
            "edges": [],
            "failures": [f"unsupported_language:{language}"],
        }
    return extract_python_import_dependencies(source, row_id=row_id, path=path).to_dict()


def main() -> None:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Extract a no-authority import/dependency modality packet from JSONL rows.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    packets = [extract_import_dependency_packet(row) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(packet, sort_keys=True) + "\n" for packet in packets), encoding="utf-8")


if __name__ == "__main__":
    main()
