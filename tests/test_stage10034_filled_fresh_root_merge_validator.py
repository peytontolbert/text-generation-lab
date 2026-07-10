from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10034_filled_fresh_root_merge_validator.py"
SUMMARY = ROOT / "runs/summaries/stage10034_filled_fresh_root_merge_validator.json"


def test_stage10034_filled_fresh_root_merge_validator() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is False
    assert summary["metrics"]["candidate_rows"] == 6
    assert summary["metrics"]["valid_candidate_rows"] == 0
    assert summary["metrics"]["failing_candidate_rows"] == 6
