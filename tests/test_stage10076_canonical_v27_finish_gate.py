import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10076_canonical_v27_finish_gate.py"
GATE = ROOT / "runs/local/artifacts/stage10076_canonical_v27_finish_gate/canonical_v27_finish_gate.json"


def test_stage10076_finish_gate_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(GATE.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["languages_with_standalone_win"] == 4
    assert payload["metrics"]["standalone_human_signoff_tasks_remaining"] == 8
