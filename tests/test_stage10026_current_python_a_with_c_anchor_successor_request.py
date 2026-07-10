from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10026_current_python_a_with_c_anchor_successor_request.py"
SUMMARY = ROOT / "runs/summaries/stage10026_current_python_a_with_c_anchor_successor_request.json"
REQUEST = ROOT / "runs/local/artifacts/stage10026_current_python_a_with_c_anchor_successor_request/current_python_a_with_c_anchor_successor_request.json"


def test_stage10026_a_with_c_anchor_successor_request() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    request = json.loads(REQUEST.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert request["passed"] is True
    assert summary["metrics"]["rows"] == 118
    assert summary["metrics"]["language_counts"]["python"] == 25
    assert summary["metrics"]["split_counts"]["train"] == 46
    assert summary["metrics"]["gap_replay_rows"] == 3
    assert summary["metrics"]["c_anchor_rows"] == 3
    assert summary["metrics"]["python_train_label_count"] == 5
    assert summary["metrics"]["python_train_signature_count"] == 5
    assert summary["metrics"]["gap_replay_reason_counts"]["python_gemma_advantage_current"] == 1
    assert summary["metrics"]["gap_replay_reason_counts"]["python_both_wrong_current"] == 2
    assert summary["metrics"]["gap_replay_reason_counts"]["python_c_anchor_preserve_current_correct_target"] == 3
