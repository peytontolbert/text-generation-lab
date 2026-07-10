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


def test_stage10114_builds_live_atlas() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10114_real_session_successor_review_priority_atlas.py",
        "stage10114_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["packet_rows"] == 41
    assert built["metrics"]["blocked_rows"] == 41
    assert built["metrics"]["high_priority_rows"] >= 2
    assert built["claim_boundary"]["supports_training_or_scoring_now"] is False
    assert built["claim_boundary"]["web_rows_should_be_reviewed_first"] is True
    assert built["claim_boundary"]["python_config_rows_are_main_shortcut_audit_slice"] is True


def test_stage10114_priority_queue_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10114_real_session_successor_review_priority_atlas.py",
        "stage10114_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 41
    assert rows[0]["review_priority_rank"] == 1
    assert rows[0]["priority_score"] >= rows[-1]["priority_score"]
    assert rows[0]["language_family"] == "web_js_ts_html"
    assert rows[0]["priority_tier"] in {"high", "medium", "low"}
