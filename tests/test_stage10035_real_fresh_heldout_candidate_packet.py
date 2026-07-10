from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10035_real_fresh_heldout_candidate_packet.py"
SUMMARY = ROOT / "runs/summaries/stage10035_real_fresh_heldout_candidate_packet.json"


def test_stage10035_real_fresh_heldout_candidate_packet() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["candidate_rows"] == 18
    assert summary["metrics"]["candidate_language_counts"]["python"] == 6
    assert summary["metrics"]["candidate_language_counts"]["c_cpp"] == 12
