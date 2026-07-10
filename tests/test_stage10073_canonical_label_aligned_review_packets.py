import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10073_canonical_label_aligned_review_packets.py"
AUDIT = ROOT / "runs/local/artifacts/stage10073_canonical_label_aligned_review_packets/canonical_label_aligned_review_audit.json"


def test_stage10073_review_packets_build():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["language_packets"] == 4
    assert payload["metrics"]["wins_100m"] == 4
