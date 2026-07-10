from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10031_python_cpp_expert_anti_cheat_review_sheet.py"
SUMMARY = ROOT / "runs/summaries/stage10031_python_cpp_expert_anti_cheat_review_sheet.json"


def test_stage10031_python_cpp_expert_anti_cheat_review_sheet() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["rows"] == 13
    assert summary["metrics"]["outcome_counts"]["both_wrong"] == 8
    assert summary["metrics"]["required_checks_per_row"] == 5
