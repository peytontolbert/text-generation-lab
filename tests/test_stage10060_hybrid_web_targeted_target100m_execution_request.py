from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_stage10059(root: Path):
    path = root / "scripts/build_stage10059_hybrid_web_targeted_geometry_successor_packet.py"
    spec = importlib.util.spec_from_file_location("stage10059", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_stage10060():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10060_hybrid_web_targeted_target100m_execution_request.py"
    spec = importlib.util.spec_from_file_location("stage10060", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_request_reflects_stage10059_successor_counts():
    root = Path(__file__).resolve().parents[1]
    stage10059 = _load_stage10059(root)
    stage10059.main()
    mod = _load_stage10060()
    built = mod.build_request()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["rows"] == 124
    assert metrics["heldout_compare_rows"] == 55
    assert metrics["stage10047_train_rows"] == 8
    assert metrics["stage10059_train_rows"] == 21
    assert metrics["language_counts"] == {
        "c_cpp": 38,
        "python": 27,
        "rust": 17,
        "web_js_ts_html": 42,
    }
    assert metrics["split_counts"] == {"eval": 38, "strict_eval": 17, "train": 69}
    req = built["surface_requests"][0]
    assert req["request_status"] == "awaiting_explicit_execution_authorization"
    assert req["required_contract_invariants"]["source_stage10059_passed"] is True
