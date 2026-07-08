from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9230_family_audit_design_output_schema_audit.py"
spec = importlib.util.spec_from_file_location("stage9230", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9230_positive_examples_pass_and_negative_cases_fail():
    audit = mod.build_audit()
    assert audit["metrics"]["positive_validation_failures"] == 0
    assert audit["metrics"]["negative_cases"] >= 18
    assert audit["metrics"]["negative_cases_rejected"] == audit["metrics"]["negative_cases"]


def test_stage9230_negative_cases_cover_forbidden_fields_and_closed_defaults():
    schema = mod.load_schema_module()
    audit = mod.build_audit()
    cases = audit["negative_case_results"]
    for field in schema.FORBIDDEN_DESIGN_FIELDS:
        assert f"forbidden_field_{field}" in cases
        assert f"forbidden_field_present:{field}" in cases[f"forbidden_field_{field}"]["failures"]
    for field in schema.CLOSED_FIELD_DEFAULTS:
        assert f"open_closed_field_{field}" in cases
        assert f"closed_field_open:{field}" in cases[f"open_closed_field_{field}"]["failures"]


def test_stage9230_keeps_execution_cleanup_arxiv_metrics_closed():
    audit = mod.build_audit()
    for metric in mod.CLOSED_METRICS:
        assert audit["metrics"][metric] is False
    assert not any(audit["authority"].values())


def test_stage9230_validation_rejects_unrejected_negative_or_open_metric():
    audit = mod.build_audit()
    audit["negative_case_results"]["forbidden_field_live_ticket_path"]["failures"] = []
    assert "negative_case_not_rejected:forbidden_field_live_ticket_path" in mod.validate_audit(audit)

    audit = mod.build_audit()
    audit["metrics"]["checkpoint_written_now"] = True
    assert "checkpoint_written_now" in mod.validate_audit(audit)
