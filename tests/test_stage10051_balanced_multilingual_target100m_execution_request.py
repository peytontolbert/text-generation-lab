from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10051_balanced_multilingual_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage10051", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_reflects_stage10050_successor_counts():
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["rows"] == 121
    assert metrics["heldout_compare_rows"] == 55
    assert metrics["language_counts"] == {
        "c_cpp": 37,
        "python": 29,
        "rust": 13,
        "web_js_ts_html": 42,
    }
    assert metrics["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 66}
    req = built["surface_requests"][0]
    assert req["request_status"] == "awaiting_explicit_execution_authorization"
    assert req["required_contract_invariants"]["source_stage10050_passed"] is True
