from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9956_v27_current_blocker_ledger.py"
    spec = importlib.util.spec_from_file_location("stage9956", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_ledger_reports_packaged_narrow_blended_path():
    mod = _load()
    ledger = mod.build_ledger()
    assert ledger["passed"] is True
    assert ledger["metrics"]["languages_with_standalone_win"] == 4
    assert ledger["metrics"]["total_pending_human_signoff_tasks"] == 8
    assert ledger["metrics"]["narrow_blended_path_fully_packaged_locally"] is True


def test_build_ledger_keeps_objective_incomplete_until_real_execution():
    mod = _load()
    ledger = mod.build_ledger()
    assert ledger["metrics"]["objective_complete"] is False
    assert ledger["narrow_blended_path"]["expected_rows"] == 72
    assert ledger["narrow_blended_path"]["expected_web_rows"] == 27
    assert "stage9950_100m_execution" in ledger["completion_boundary"]["still_requires_real_execution_or_external_input"]
