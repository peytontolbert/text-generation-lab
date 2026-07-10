import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10082_canonical_label_aligned_shortcut_validity_audit.py"
AUDIT = ROOT / "runs/local/artifacts/stage10082_canonical_label_aligned_shortcut_validity_audit/canonical_label_aligned_shortcut_validity_audit.json"


def test_stage10082_shortcut_validity_audit_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["metrics"]["shared_rows"] == 55
    assert payload["metrics"]["rows_with_choice_permutation_metadata"] == 37
    assert payload["metrics"]["rows_with_opaque_choice_surface"] == 37
    assert payload["metrics"]["canonical_mismatch_rows"] == 0
    assert payload["metrics"]["hundred_m_macro_exact"] > payload["metrics"]["global_majority_exact"]
    assert payload["metrics"]["hundred_m_macro_exact"] > payload["metrics"]["macro_per_language_majority_exact"]
    assert payload["metrics"]["source_heldout_claim_supported"] is False

    assert payload["findings"]["permutation_coverage_scope"]["supported"] is False
