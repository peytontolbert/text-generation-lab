import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10077_canonical_v27_closeout_packet.py"
PACKET = ROOT / "runs/local/artifacts/stage10077_canonical_v27_closeout_packet/canonical_v27_closeout_packet.json"


def test_stage10077_closeout_packet_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(PACKET.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["language_packets"] == 4
    assert payload["metrics"]["languages_with_external_harness_handoff"] == 4
