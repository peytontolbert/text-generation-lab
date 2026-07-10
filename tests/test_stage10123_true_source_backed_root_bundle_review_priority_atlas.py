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


def test_stage10123_builds_priority_atlas() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10123_true_source_backed_root_bundle_review_priority_atlas.py",
        "stage10123_live",
    )
    built = mod.build_priority_atlas()
    assert built["passed"] is True
    assert built["atlas"]["metrics"]["bundle_count"] == 8
    assert built["atlas"]["metrics"]["first_wave_bundle_count"] == 6
    assert built["atlas"]["metrics"]["first_wave_language_counts"] == {"c_cpp": 2, "python": 2, "web_js_ts_html": 2}
    assert built["atlas"]["metrics"]["rust_replenishment_required"] is True
    assert built["workbook"]["metrics"]["signoff_tasks"] == 18


def test_stage10123_prioritizes_web_and_multilingual_coverage() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10123_true_source_backed_root_bundle_review_priority_atlas.py",
        "stage10123_queue",
    )
    built = mod.build_priority_atlas()
    queue = built["queue_rows"]
    assert queue[0]["language_family"] == "web_js_ts_html"
    assert queue[1]["language_family"] == "web_js_ts_html"
    wave = built["atlas"]["recommended_first_wave"]["bundle_ids"]
    queue_by_id = {row["bundle_id"]: row for row in queue}
    languages = {queue_by_id[bundle_id]["language_family"] for bundle_id in wave}
    assert languages == {"web_js_ts_html", "python", "c_cpp"}


def test_stage10123_main_writes_artifacts() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10123_true_source_backed_root_bundle_review_priority_atlas.py",
        "stage10123_written",
    )
    mod.main()
    atlas = json.loads(mod.ATLAS.read_text(encoding="utf-8"))
    workbook = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    assert atlas["metrics"]["first_wave_bundle_count"] == 6
    assert workbook["metrics"]["signoff_tasks"] == 18
