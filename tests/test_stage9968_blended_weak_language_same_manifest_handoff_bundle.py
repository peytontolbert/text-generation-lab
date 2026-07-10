from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9968_blended_weak_language_same_manifest_handoff_bundle.py"
    spec = importlib.util.spec_from_file_location("stage9968", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_bundle_reflects_successor_same_manifest_contract():
    import build_stage9966_blended_weak_language_target100m_execution_request as stage9966
    import build_stage9967_blended_weak_language_execution_readiness_gate as stage9967
    stage9966.main()
    stage9967.main()
    mod = _load()
    built = mod.build_bundle()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["hundred_m_future_stage"] == 9965
    assert metrics["gemma_future_stage"] == 9971
    assert metrics["same_manifest_compare_rows"] == 80
    assert metrics["row_contract_ok"] is True
