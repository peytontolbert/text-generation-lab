from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10030_python_cpp_fresh_root_replenishment_request.py"
SUMMARY = ROOT / "runs/summaries/stage10030_python_cpp_fresh_root_replenishment_request.json"


def test_stage10030_python_cpp_fresh_root_replenishment_request() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["rows"] == 9
    assert summary["metrics"]["language_counts"]["python"] == 3
    assert summary["metrics"]["language_counts"]["c_cpp"] == 6
    assert summary["metrics"]["request_group_count"] == 6
