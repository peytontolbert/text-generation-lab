from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9231_frontier_after_audit_design_schema_audit.py"
spec = importlib.util.spec_from_file_location("stage9231", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9231_records_schema_audits_and_no_request():
    card = mod.build_card()
    assert "request_schema_exists_and_negative_audited" in card["frontier_facts"]
    assert "family_audit_design_output_schema_negative_audited" in card["frontier_facts"]
    assert "no_valid_request_present" in card["frontier_facts"]
    assert "no_family_selected" in card["frontier_facts"]
    assert card["metrics"]["valid_request_present"] is False


def test_stage9231_blocks_execution_cleanup_arxiv_and_has_resume_pointers():
    card = mod.build_card()
    assert "invoke_trainer" in card["blocked_actions"]
    assert "execute_cleanup" in card["blocked_actions"]
    assert "read_write_or_mine_arxiv" in card["blocked_actions"]
    assert "audit_design_schema_audit" in card["resume_pointers"]
    assert "registry" in card["resume_pointers"]


def test_stage9231_keeps_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())


def test_stage9231_validation_rejects_open_metric_or_missing_required_fact():
    card = mod.build_card()
    card["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in mod.validate_card(card)

    card = mod.build_card()
    card["frontier_facts"].remove("no_family_selected")
    assert "missing_frontier_fact:no_family_selected" in mod.validate_card(card)

    card = mod.build_card()
    card["blocked_actions"].remove("execute_cleanup")
    assert "missing_blocked_action:execute_cleanup" in mod.validate_card(card)
