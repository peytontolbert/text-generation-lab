from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage10014_quarantined_blended_weak_language_same_manifest_handoff_bundle.py"
    spec = importlib.util.spec_from_file_location("stage10014", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_bundle_reflects_quarantined_same_manifest_contract():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage10012_quarantined_blended_weak_language_execution_review as stage10012
    import build_stage10013_quarantined_blended_weak_language_target100m_execution_request as stage10013

    stage10012.main()
    stage10013.main()
    mod = _load()
    built = mod.build_bundle()
    assert built["passed"] is True
    metrics = built["metrics"]
    assert metrics["hundred_m_future_stage"] == 10013
    assert metrics["gemma_future_stage"] == 10015
    assert metrics["same_manifest_compare_rows"] == 72
    assert metrics["row_contract_ok"] is True
