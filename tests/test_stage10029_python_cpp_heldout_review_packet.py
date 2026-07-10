from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10029_python_cpp_heldout_review_packet.py"
SUMMARY = ROOT / "runs/summaries/stage10029_python_cpp_heldout_review_packet.json"


def test_stage10029_python_cpp_heldout_review_packet() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["rows"] == 13
    assert summary["metrics"]["language_counts"]["python"] == 5
    assert summary["metrics"]["language_counts"]["c_cpp"] == 8
