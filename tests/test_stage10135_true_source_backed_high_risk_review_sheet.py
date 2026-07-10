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


def test_stage10135_builds_live_sheet() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10135_true_source_backed_high_risk_review_sheet.py",
        "stage10135_live",
    )
    built = mod.build_sheet()
    assert built["passed"] is True
    assert built["metrics"]["high_risk_rows"] == 4
    assert built["metrics"]["web_rows_included"] == 2
    assert built["metrics"]["rows_without_selected_tests"] == 4
    assert built["metrics"]["highest_shortcut_risk"] == 8


def test_stage10135_main_writes_sheet() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10135_true_source_backed_high_risk_review_sheet.py",
        "stage10135_written",
    )
    mod.main()
    sheet = json.loads(mod.SHEET.read_text(encoding="utf-8"))
    assert sheet["metrics"]["high_risk_rows"] == 4
    assert sheet["rows"][0]["language_family"] == "web_js_ts_html"
