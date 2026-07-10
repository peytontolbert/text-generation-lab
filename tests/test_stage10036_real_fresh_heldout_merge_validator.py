from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10036_real_fresh_heldout_merge_validator.py"
SUMMARY = ROOT / "runs/summaries/stage10036_real_fresh_heldout_merge_validator.json"


def test_stage10036_real_fresh_heldout_merge_validator() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["candidate_rows"] == 18
    assert summary["metrics"]["valid_candidate_rows"] == 18
    assert summary["metrics"]["merged_rows"] == 95
    assert summary["metrics"]["actual_valid_counts"] == {
        "c_cpp:A": 3,
        "c_cpp:B": 3,
        "c_cpp:D": 3,
        "c_cpp:E": 3,
        "python:A": 3,
        "python:D": 3,
    }
