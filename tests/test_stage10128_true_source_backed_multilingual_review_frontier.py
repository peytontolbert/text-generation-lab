from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_stage10128_builds_four_language_frontier() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10128_true_source_backed_multilingual_review_frontier.py",
        "stage10128_live",
    )
    built = mod.build_frontier()
    assert built["passed"] is True
    assert built["atlas"]["metrics"]["bundle_count"] == 12
    assert built["atlas"]["metrics"]["queue_language_counts"] == {
        "c_cpp": 3,
        "python": 3,
        "rust": 4,
        "web_js_ts_html": 2,
    }
    assert built["atlas"]["metrics"]["first_wave_language_counts"] == {
        "c_cpp": 2,
        "python": 2,
        "rust": 2,
        "web_js_ts_html": 2,
    }
    assert built["workbook"]["metrics"]["signoff_tasks"] == 24


def test_stage10128_first_wave_includes_rust() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10128_true_source_backed_multilingual_review_frontier.py",
        "stage10128_wave",
    )
    built = mod.build_frontier()
    queue_by_id = {row["bundle_id"]: row for row in built["queue_rows"]}
    wave_ids = built["atlas"]["recommended_first_wave"]["bundle_ids"]
    languages = Counter(queue_by_id[bundle_id]["language_family"] for bundle_id in wave_ids)
    assert languages == Counter({"web_js_ts_html": 2, "python": 2, "c_cpp": 2, "rust": 2})


def test_stage10128_main_writes_frontier() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10128_true_source_backed_multilingual_review_frontier.py",
        "stage10128_written",
    )
    mod.main()
    atlas = json.loads(mod.ATLAS.read_text(encoding="utf-8"))
    workbook = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    assert atlas["metrics"]["four_language_review_ready"] is True
    assert workbook["metrics"]["signoff_tasks"] == 24
