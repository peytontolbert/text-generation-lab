import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10072_canonical_label_aligned_same_manifest_comparison_audit.py"
AUDIT = ROOT / "runs/local/artifacts/stage10072_canonical_label_aligned_same_manifest_comparison_audit/canonical_label_aligned_same_manifest_comparison_audit.json"


def test_stage10072_comparison_audit_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["shared_rows"] == 55
    assert payload["metrics"]["wins_100m"] == 4
