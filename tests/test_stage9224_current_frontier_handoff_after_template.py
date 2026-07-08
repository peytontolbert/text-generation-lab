from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9224_current_frontier_handoff_after_template.py"
spec = importlib.util.spec_from_file_location("stage9224", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9224_records_resume_pointers_and_valid_branches():
    card = mod.build_card()
    assert "inactive_template" in card["resume_pointers"]
    assert "gap_map" in card["resume_pointers"]
    assert "stop_and_wait_for_explicit_one_family_request" in card["only_valid_next_branches"]
    assert "if_user_selects_exactly_one_family_build_family_specific_final_preexecution_audit_design_only" in card["only_valid_next_branches"]


def test_stage9224_blocks_invalid_training_cleanup_arxiv_branches():
    card = mod.build_card()
    assert "run_trainer" in card["invalid_next_branches"]
    assert "execute_cleanup" in card["invalid_next_branches"]
    assert "read_write_or_mine_arxiv" in card["invalid_next_branches"]
    for metric in mod.CLOSED_METRICS:
        assert card["metrics"][metric] is False


def test_stage9224_validation_rejects_open_metric_or_missing_branch():
    card = mod.build_card()
    card["metrics"]["cleanup_executed_now"] = True
    assert "cleanup_executed_now" in mod.validate_card(card)

    card = mod.build_card()
    card["only_valid_next_branches"] = []
    assert "missing_valid_branch:stop_and_wait_for_explicit_one_family_request" in mod.validate_card(card)

    card = mod.build_card()
    card["invalid_next_branches"].remove("run_trainer")
    assert "missing_invalid_branch:run_trainer" in mod.validate_card(card)
