from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10032_python_cpp_fresh_root_builder_workbook.py"
SUMMARY = ROOT / "runs/summaries/stage10032_python_cpp_fresh_root_builder_workbook.json"


def test_stage10032_python_cpp_fresh_root_builder_workbook() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["tasks"] == 6
    assert summary["metrics"]["languages"] == ["c_cpp", "python"]
    assert summary["metrics"]["total_requested_fresh_roots"] >= 18
