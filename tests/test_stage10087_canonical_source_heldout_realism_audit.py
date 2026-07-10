import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_stage10087_canonical_source_heldout_realism_audit.py"
AUDIT = ROOT / "runs/local/artifacts/stage10087_canonical_source_heldout_realism_audit/canonical_source_heldout_realism_audit.json"
SPEC = ROOT / "runs/local/artifacts/stage10087_canonical_source_heldout_realism_audit/canonical_source_heldout_realistic_successor_spec.json"


def test_stage10087_realism_audit_builds():
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=ROOT)
    payload = json.loads(AUDIT.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["claim_boundary"]["structured_edit_target_taxonomy_supported"] is True
    assert payload["claim_boundary"]["serious_software_maintenance_eval_supported"] is False
    assert payload["metrics"]["heldout_rows"] == 55
    assert payload["metrics"]["level_counts"] == {"L0": 55}
    assert payload["metrics"]["rows_with_explicit_surface_candidate_choices"] == 37
    assert payload["metrics"]["present_field_groups"]["trace_or_stack"] == 0
    assert payload["metrics"]["present_field_groups"]["code_snippets"] == 0
    assert spec["preserve_from_stage10083"]["canonical_label_map"]["TARGET_SYMBOL"] == "C"
    assert "failure_text" in spec["required_visible_fields_by_level"]["L2"]
