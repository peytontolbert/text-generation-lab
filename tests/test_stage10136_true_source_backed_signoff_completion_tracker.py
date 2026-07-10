from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10136_builds_live_tracker() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10136_true_source_backed_signoff_completion_tracker.py",
        "stage10136_live",
    )
    built = mod.build_tracker()
    assert built["passed"] is True
    assert built["metrics"]["bundle_count"] == 8
    assert built["metrics"]["bundles_with_pending_rubric"] == 8
    assert built["metrics"]["bundles_with_pending_anti_cheat"] == 8
    assert built["metrics"]["bundles_with_pending_gold"] == 8
    assert built["metrics"]["total_missing_gold_perspective_fields"] == 8 * 8 * 3


def test_stage10136_main_writes_tracker() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10136_true_source_backed_signoff_completion_tracker.py",
        "stage10136_written",
    )
    mod.main()
    tracker = json.loads(mod.TRACKER.read_text(encoding="utf-8"))
    assert tracker["metrics"]["bundle_count"] == 8
    assert sorted(tracker["rows"][0]["rubric_missing_fields"]) == [
        "rubric_bundle_not_marked_valid",
        "rubric_missing_decision_rationale",
        "rubric_missing_reviewer_id",
        "rubric_status_not_completed",
    ]
