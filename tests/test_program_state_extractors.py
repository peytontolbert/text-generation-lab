from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from program_state_ast_cst_extractor import extract_python_ast
from program_state_import_dependency_extractor import extract_python_import_dependencies
from program_state_symbol_table_extractor import extract_python_symbols


SAMPLE = """
import os
from pathlib import Path as P


class Greeter:
    def hello(self, name: str) -> str:
        return f"hello {name}"


def main(path: str) -> str:
    root = P(path)
    return Greeter().hello(os.fspath(root))
"""


def test_ast_extractor_emits_opaque_nodes_and_edges() -> None:
    packet = extract_python_ast(SAMPLE, row_id="row_a", path="pkg/example.py")
    assert packet.failures == []
    assert packet.nodes
    assert packet.edges
    assert any(node["node_type"] == "FunctionDef" for node in packet.nodes)
    assert any(edge["edge_type"] == "ast_child" for edge in packet.edges)
    joined_ids = " ".join(node["node_id"] for node in packet.nodes)
    assert "Greeter" not in joined_ids
    assert "main" not in joined_ids


def test_symbol_table_extractor_emits_defs_imports_calls_and_signatures() -> None:
    packet = extract_python_symbols(SAMPLE, row_id="row_a", path="pkg/example.py")
    assert packet.failures == []
    kinds = {symbol["symbol_kind"] for symbol in packet.symbols}
    assert "import" in kinds
    assert "class" in kinds
    assert "function" in kinds
    assert "method" in kinds
    assert "callsite" in kinds
    main = next(symbol for symbol in packet.symbols if symbol["name"] == "main")
    assert main["signature"]["returns"] == "str"
    assert any(edge["edge_type"] in {"imports", "calls", "defines"} for edge in packet.edges)


def test_import_dependency_extractor_emits_package_edges() -> None:
    packet = extract_python_import_dependencies(SAMPLE, row_id="row_a", path="pkg/example.py")
    assert packet.failures == []
    modules = {dep["module"] for dep in packet.dependencies}
    packages = {dep["package"] for dep in packet.dependencies}
    assert "os" in modules
    assert "pathlib" in modules
    assert "pathlib" in packages
    assert all(edge["edge_type"] == "imports" for edge in packet.edges)


def test_extractors_report_syntax_error_without_throwing() -> None:
    bad = "def nope(:\n"
    ast_packet = extract_python_ast(bad)
    sym_packet = extract_python_symbols(bad)
    dep_packet = extract_python_import_dependencies(bad)
    assert ast_packet.failures
    assert sym_packet.failures
    assert dep_packet.failures
