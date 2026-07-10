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


def test_stage10115_builds_live_workbook() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10115_real_session_successor_first_wave_signoff_workbook.py",
        "stage10115_live",
    )
    built = mod.build_workbook()
    assert built["passed"] is True
    assert built["metrics"]["first_wave_rows"] == 15
    assert built["metrics"]["signoff_tasks"] == 30
    assert built["metrics"]["wave_language_counts"] == {"c_cpp": 9, "python": 4, "web_js_ts_html": 2}


def test_stage10115_workbook_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10115_real_session_successor_first_wave_signoff_workbook.py",
        "stage10115_written",
    )
    mod.main()
    payload = json.loads(mod.WORKBOOK.read_text(encoding="utf-8"))
    rows = payload["rows"]
    assert len(rows) == 30
    assert rows[0]["wave_rank"] == 1
    assert rows[0]["language_family"] == "web_js_ts_html"
    assert rows[0]["task"] == "expert_maintainer_rubric_review"
    assert rows[1]["task"] == "cell_specific_anti_cheat_review"
