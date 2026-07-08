from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9228_request_to_audit_instantiation_blocker.py"
spec = importlib.util.spec_from_file_location("stage9228", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9228_request_chain_keeps_design_before_live_ticket():
    card = mod.build_card()
    chain = card["request_to_audit_chain"]
    assert chain.index("family_specific_final_preexecution_audit_design_audited") < chain.index("only_then_consider_separate_live_ticket_design")
    assert "family_specific_final_preexecution_audit_design_json" in card["audit_design_only_outputs"]
    assert "live_ticket" in card["forbidden_design_outputs"]


def test_stage9228_blocks_training_cleanup_arxiv_without_valid_request():
    card = mod.build_card()
    assert "cannot_invoke_trainer" in card["blockers_when_no_valid_request"]
    assert "cannot_execute_cleanup" in card["blockers_when_no_valid_request"]
    assert "cannot_access_arxiv" in card["blockers_when_no_valid_request"]
    assert "trainer_command_execution" in card["forbidden_design_outputs"]
    assert "arxiv_inventory" in card["forbidden_design_outputs"]


def test_stage9228_keeps_all_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())


def test_stage9228_validation_rejects_open_metric_or_missing_blocks():
    card = mod.build_card()
    card["metrics"]["live_ticket_materialized_now"] = True
    assert "live_ticket_materialized_now" in mod.validate_card(card)

    card = mod.build_card()
    card["blockers_when_no_valid_request"].remove("cannot_execute_cleanup")
    assert "missing_blocker:cannot_execute_cleanup" in mod.validate_card(card)

    card = mod.build_card()
    card["forbidden_design_outputs"].remove("checkpoint")
    assert "missing_forbidden_output:checkpoint" in mod.validate_card(card)
