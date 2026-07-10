from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load(module_name: str, filename: str):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts" / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_stage10038_bundle_reflects_expanded_source_heldout_contract():
    stage10037 = _load("stage10037", "build_stage10037_expanded_source_heldout_target100m_execution_request.py")
    built_request = stage10037.build_request()
    assert built_request["passed"] is True

    stage10038 = _load("stage10038", "build_stage10038_expanded_source_heldout_same_manifest_handoff_bundle.py")
    built = stage10038.build_bundle()
    assert built["passed"] is True
    assert built["metrics"]["same_manifest_compare_rows"] == 55
    assert built["metrics"]["row_contract_ok"] is True
    contract = built["handoff_bundle"]["row_contract"]
    assert contract["hundred_m_rows"] == 95
    assert contract["hundred_m_python_rows"] == 19
    assert contract["hundred_m_c_cpp_rows"] == 30
    assert contract["hundred_m_rust_rows"] == 11
    assert contract["hundred_m_web_rows"] == 35
