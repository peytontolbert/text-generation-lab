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


def test_stage10121_builds_signoff_workbook() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10121_true_source_backed_root_bundle_signoff_workbook.py",
        "stage10121_live",
    )
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["signoff_tasks"] == 24
    assert built["metrics"]["perspective_gold_tasks"] == 8
    assert built["metrics"]["bundle_count"] == 8


def test_stage10121_writes_gold_stub() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10121_true_source_backed_root_bundle_signoff_workbook.py",
        "stage10121_written",
    )
    mod.main()
    payload = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    gold_row = next(row for row in payload["rows"] if row["task"] == "perspective_gold_adjudication")
    gold = json.loads((ROOT / gold_row["review_file"]).read_text(encoding="utf-8"))
    assert gold["status"] == "pending_human_review"
    assert len(gold["perspective_gold_answers"]) == 8
    assert gold["bundle_gold_ready_for_eval"] is False
