from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9747_truthful_standalone_acceptance_evidence_bridge.py"
    spec = importlib.util.spec_from_file_location("stage9747", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage9747_truthfully_counts_supported_cells():
    mod = _load()
    bridge = mod.build_bridge()
    assert bridge["failures"] == []
    assert bridge["metrics"]["standalone_cells_with_truthful_100m_side_support"] == 13
    assert bridge["metrics"]["full_product_harness_cells_with_truthful_support"] == 0
    assert bridge["metrics"]["unsupported_symbol_binding_languages"] == ["c_cpp", "rust", "web_js_ts_html"]

    python_symbol = next(
        row for row in bridge["records"]
        if row["cell_key"] == "standalone_100m_weights::python::symbol_binding"
    )
    rust_symbol = next(
        row for row in bridge["records"]
        if row["cell_key"] == "standalone_100m_weights::rust::symbol_binding"
    )
    assert python_symbol["attached_evidence"]
    assert "language_slice_scores" not in python_symbol["missing_required_evidence"]
    assert rust_symbol["attached_evidence"] == []
    assert "language_slice_scores" in rust_symbol["missing_required_evidence"]
