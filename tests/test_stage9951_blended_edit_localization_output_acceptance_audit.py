from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9951_blended_edit_localization_output_acceptance_audit.py"
    spec = importlib.util.spec_from_file_location("stage9951", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_audit_targets_stage9950_edit_localization_candidate():
    mod = _load()
    audit = mod.build_audit()
    assert audit["passed"] is True
    assert audit["future_run"]["future_stage"] == 9950
    assert audit["future_run"]["selected_surface"] == "edit_localization"
    assert audit["blend_invariants"]["expected_rows"] == 72
    assert audit["blend_invariants"]["expected_web_rows"] == 27


def test_pending_artifacts_match_required_runtime_artifacts_before_execution():
    mod = _load()
    audit = mod.build_audit()
    assert audit["metrics"]["acceptance_ready"] is False
    assert audit["metrics"]["required_runtime_artifacts"] == len(audit["pending_artifacts"])
    assert audit["metrics"]["artifacts_present"] == 0
