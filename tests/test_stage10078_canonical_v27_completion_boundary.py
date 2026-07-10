import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10078_canonical_v27_completion_boundary.py"
BOUNDARY = ROOT / "runs/local/artifacts/stage10078_canonical_v27_completion_boundary/canonical_v27_completion_boundary.json"


def test_stage10078_completion_boundary_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["languages_with_harness_acceptance_ready"] == 0
    assert payload["metrics"]["total_pending_harness_artifacts"] == 28
