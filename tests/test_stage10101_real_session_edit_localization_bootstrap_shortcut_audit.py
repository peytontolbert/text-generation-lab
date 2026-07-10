from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10101_bootstrap_shortcut_audit_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10101_real_session_edit_localization_bootstrap_shortcut_audit.py",
        "stage10101",
    )
    audit, rows = mod.build()
    assert audit["passed"] is True
    assert len(rows) == 56
    assert audit["metrics"]["unique_target_rows"] == 19
    assert audit["metrics"]["unique_target_counts"] == {"TARGET_FILE": 19}
    assert audit["metrics"]["changed_path_signature_majority_exact_on_unique_rows"] == 1.0
    assert audit["claim_boundary"]["real_session_inventory_is_evaluator_ready_for_edit_localization"] is False
    assert audit["claim_boundary"]["usable_as_source_evidence_reservoir"] is True
