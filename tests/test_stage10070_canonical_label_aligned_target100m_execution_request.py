import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10070_canonical_label_aligned_target100m_execution_request.py"
REQUEST = ROOT / "runs/local/artifacts/stage10070_canonical_label_aligned_target100m_execution_request/canonical_label_aligned_target100m_execution_request.json"


def test_stage10070_execution_request_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(REQUEST.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["rows"] == 142
    assert payload["metrics"]["heldout_compare_rows"] == 55
