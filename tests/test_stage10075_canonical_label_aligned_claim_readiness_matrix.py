import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10075_canonical_label_aligned_claim_readiness_matrix.py"
MATRIX = ROOT / "runs/local/artifacts/stage10075_canonical_label_aligned_claim_readiness_matrix/canonical_label_aligned_claim_readiness_matrix.json"


def test_stage10075_claim_readiness_matrix_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["standalone_edit_localization_wins"] == 4
    assert payload["metrics"]["pending_signoff_tasks"] == 8
