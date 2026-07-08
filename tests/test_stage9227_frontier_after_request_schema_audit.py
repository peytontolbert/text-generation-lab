from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9227_frontier_after_request_schema_audit.py"
spec = importlib.util.spec_from_file_location("stage9227", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9227_records_no_valid_request_and_no_family_selection():
    card = mod.build_card()
    assert "no_valid_request_has_been_submitted" in card["frontier_status"]
    assert "no_family_selected" in card["frontier_status"]
    assert "no_live_ticket_materialized" in card["frontier_status"]
    assert card["metrics"]["valid_request_present"] is False
    assert card["metrics"]["family_selected_now"] is False


def test_stage9227_valid_next_actions_are_non_execution_only():
    card = mod.build_card()
    assert "wait_for_valid_explicit_one_family_request" in card["valid_next_actions"]
    assert "continue_no_execution_central_graph_review" in card["valid_next_actions"]
    assert "invoke_trainer" in card["blocked_actions"]
    assert "execute_cleanup" in card["blocked_actions"]
    assert "read_write_or_mine_arxiv" in card["blocked_actions"]


def test_stage9227_keeps_all_closed_metrics_and_authority_closed():
    card = mod.build_card()
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False
    assert not any(card["authority"].values())


def test_stage9227_validation_rejects_open_metric_or_missing_block():
    card = mod.build_card()
    card["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in mod.validate_card(card)

    card = mod.build_card()
    card["blocked_actions"].remove("execute_cleanup")
    assert "missing_blocked_action:execute_cleanup" in mod.validate_card(card)

    card = mod.build_card()
    card["frontier_status"].remove("no_family_selected")
    assert "missing_frontier_status:no_family_selected" in mod.validate_card(card)
