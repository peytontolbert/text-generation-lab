import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10074_canonical_label_aligned_signoff_workbook.py"
WORKBOOK = ROOT / "runs/local/artifacts/stage10074_canonical_label_aligned_signoff_workbook/canonical_label_aligned_signoff_workbook.json"


def test_stage10074_signoff_workbook_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(WORKBOOK.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["signoff_tasks"] == 8
    assert payload["metrics"]["wins_100m"] == 4
