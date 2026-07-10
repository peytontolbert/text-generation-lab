from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage10028_deduped_source_heldout_same_manifest_comparison_audit.py"
SUMMARY = ROOT / "runs/summaries/stage10028_deduped_source_heldout_same_manifest_comparison_audit.json"


def test_stage10028_deduped_source_heldout_comparison_audit() -> None:
    subprocess.run(["python", str(SCRIPT)], cwd=ROOT, check=True)
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    assert summary["passed"] is True
    assert summary["metrics"]["heldout_eval_rows"] == 37
    assert summary["metrics"]["comparison_rows"] == 37
    assert summary["metrics"]["rows_100m_present"] == 37
    assert summary["metrics"]["rows_gemma_eval_present"] == 37
    assert summary["metrics"]["wins_100m"] == 4
    assert summary["metrics"]["wins_gemma"] == 0
    assert summary["metrics"]["per_language"]["python"]["rows"] == 5
    assert summary["metrics"]["per_language"]["c_cpp"]["rows"] == 8
