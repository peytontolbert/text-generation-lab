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


def test_stage10127_builds_rust_review_packets_and_signoff() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10127_true_source_backed_rust_review_packets_and_signoff.py",
        "stage10127_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["manifest"]["metrics"]["review_bundles"] == 4
    assert built["workbook"]["metrics"]["signoff_tasks"] == 12
    assert built["workbook"]["metrics"]["perspective_gold_tasks"] == 4


def test_stage10127_writes_gold_stub_and_packet_paths() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10127_true_source_backed_rust_review_packets_and_signoff.py",
        "stage10127_written",
    )
    mod.main()
    workbook = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    gold_row = next(row for row in workbook["rows"] if row["task"] == "perspective_gold_adjudication")
    gold = json.loads((ROOT / gold_row["review_file"]).read_text(encoding="utf-8"))
    assert gold["status"] == "pending_human_review"
    assert len(gold["perspective_gold_answers"]) == 8
    manifest = json.loads(mod.MANIFEST.read_text(encoding="utf-8"))
    assert manifest["metrics"]["language_counts"] == {"rust": 4}


def test_stage10127_packet_files_exist() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10127_true_source_backed_rust_review_packets_and_signoff.py",
        "stage10127_paths",
    )
    built = mod.build()
    first = built["packets"][0]
    paths = first["review_packet_paths"]
    for key in [
        "expert_maintainer_rubric_review",
        "anti_cheat_review_card",
        "rubric_recommendation_draft",
        "anti_cheat_recommendation_draft",
        "perspective_gold_adjudication",
    ]:
        assert (ROOT / paths[key]).exists()
