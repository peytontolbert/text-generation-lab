from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10033_python_cpp_fresh_root_scaffold_packet.py"
SUMMARY = ROOT / "runs/summaries/stage10033_python_cpp_fresh_root_scaffold_packet.json"


def test_stage10033_python_cpp_fresh_root_scaffold_packet() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["tasks"] == 6
    assert summary["metrics"]["scaffold_rows"] == 6
    assert summary["metrics"]["languages"] == ["c_cpp", "python"]
