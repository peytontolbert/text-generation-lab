from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9226_explicit_one_family_request_schema_audit.py"
spec = importlib.util.spec_from_file_location("stage9226", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9226_rejects_all_negative_cases():
    audit = mod.build_audit()
    assert audit["metrics"]["negative_cases"] >= 12
    assert audit["metrics"]["negative_cases_rejected"] == audit["metrics"]["negative_cases"]
    assert audit["positive_template_failures"] == []


def test_stage9226_negative_cases_cover_execution_cleanup_arxiv_runtime():
    audit = mod.build_audit()
    cases = audit["negative_case_results"]
    assert "trainer_invocation_requested" in cases["trainer_invocation_requested"]["failures"]
    assert "model_forward_or_generation_requested" in cases["model_forward_or_generation_requested"]["failures"]
    assert "cleanup_requested" in cases["cleanup_requested"]["failures"]
    assert "arxiv_access_requested" in cases["arxiv_access_requested"]["failures"]
    assert "runtime_requested" in cases["runtime_requested"]["failures"]
    assert "checkpoint_export_requested" in cases["checkpoint_export_requested"]["failures"]


def test_stage9226_keeps_metrics_and_authority_closed():
    audit = mod.build_audit()
    for key in [
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "cleanup_authorized_now",
        "cleanup_executed_now",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        assert audit["metrics"][key] is False
    assert not any(audit["authority"].values())


def test_stage9226_validation_rejects_unrejected_negative_or_open_metric():
    audit = mod.build_audit()
    audit["negative_case_results"]["cleanup_requested"]["failures"] = []
    assert "negative_case_not_rejected:cleanup_requested" in mod.validate_audit(audit)

    audit = mod.build_audit()
    audit["metrics"]["cleanup_executed_now"] = True
    assert "cleanup_executed_now" in mod.validate_audit(audit)
