from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10048_python_symbol_test_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage10048", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_reflects_stage10047_successor_counts():
    mod = _load()
    built = mod.build_request()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["rows"] == 103
    assert metrics["heldout_compare_rows"] == 55
    assert metrics["stage10047_train_rows"] == 8
    assert metrics["stage10047_heldout_rows"] == 0
    assert metrics["language_counts"] == {
        "c_cpp": 30,
        "python": 27,
        "rust": 11,
        "web_js_ts_html": 35,
    }
    assert metrics["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 48}
    req = built["surface_requests"][0]
    assert req["request_status"] == "awaiting_explicit_execution_authorization"
    assert req["required_contract_invariants"]["source_stage10047_passed"] is True
