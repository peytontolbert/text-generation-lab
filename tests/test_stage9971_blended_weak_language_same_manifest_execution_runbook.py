from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9971_blended_weak_language_same_manifest_execution_runbook.py"
    spec = importlib.util.spec_from_file_location("stage9971", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_runbook_reflects_weak_language_same_manifest_contract():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import build_stage9970_blended_weak_language_same_manifest_signoff_workbook as stage9970

    stage9970.main()
    mod = _load()
    built = mod.build_runbook()
    assert built["passed"] is True
    assert built["metrics"]["hundred_m_future_stage"] == 9965
    assert built["metrics"]["gemma_future_stage"] == 9971
    assert built["metrics"]["same_manifest_compare_rows"] == 80
    assert [row["step_id"] for row in built["steps"]] == [
        "precheck_authorization_and_disk",
        "run_stage9965_hundred_m",
        "audit_stage9965_outputs",
        "run_stage9971_gemma",
        "compare_same_manifest_only",
    ]
