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


def test_stage10107_builds_live_atlas() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10107_real_session_review_priority_shortcut_atlas.py",
        "stage10107_live",
    )
    built = mod.build()
    assert built["passed"] is True
    assert built["metrics"]["packet_rows"] == 33
    assert built["metrics"]["blocked_rows"] == 33
    assert built["metrics"]["high_risk_rows"] >= 1
    assert built["claim_boundary"]["supports_training_or_scoring_now"] is False
    assert built["claim_boundary"]["python_file_vs_test_rows_dominate_shortcut_risk"] is True


def test_stage10107_priority_queue_written() -> None:
    mod = _load(
        ROOT / "scripts/build_stage10107_real_session_review_priority_shortcut_atlas.py",
        "stage10107_written",
    )
    mod.main()
    rows = [json.loads(line) for line in mod.QUEUE.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 33
    assert rows[0]["review_priority_rank"] == 1
    assert rows[0]["risk_score"] >= rows[-1]["risk_score"]
    assert rows[0]["risk_severity"] in {"high", "medium", "low"}
