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


def test_stage10112_claim_bridge_builds() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10112_real_session_successor_claim_bridge_after_review_workbook.py",
        "stage10112",
    )
    built = mod.build_refresh()
    assert built["passed"] is True
    assert built["metrics"]["bridge_records"] == 41
    assert built["metrics"]["rows_with_workbook_support"] == 41
    assert built["metrics"]["rows_machine_complete_but_review_blocked"] == 41
    assert built["claim_boundary"]["supports_training_or_scoring_now"] is False
    first = built["records"][0]
    assert first["claim_status"] == "blocked_pending_human_review_confirmation"

