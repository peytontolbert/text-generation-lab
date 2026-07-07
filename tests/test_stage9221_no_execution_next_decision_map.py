from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPT = ROOT / "scripts/build_stage9221_no_execution_next_decision_map.py"
spec = importlib.util.spec_from_file_location("stage9221", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)


def test_stage9221_maps_all_three_families_without_live_status():
    card = mod.build_card()
    assert set(card["family_decisions"]) == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }
    for spec in card["family_decisions"].values():
        assert spec["status"] == "inactive_ticket_covered_not_live"
        assert spec["requires_before_any_run"]


def test_stage9221_default_branch_blocks_live_ticket_training_cleanup_and_arxiv():
    card = mod.build_card()
    assert "do_not_materialize_live_ticket" in card["default_branch_when_no_family_selected"]
    assert "trainer_execution" in card["forbidden_always_without_explicit_live_ticket"]
    assert "cleanup_execution" in card["forbidden_always_without_explicit_live_ticket"]
    assert "arxiv_access_or_mining" in card["forbidden_always_without_explicit_live_ticket"]
    assert card["metrics"]["trainer_executed_now"] is False
    assert card["metrics"]["cleanup_authorized_now"] is False


def test_stage9221_validation_rejects_open_execution_or_live_family_status():
    card = mod.build_card()
    card["metrics"]["next_stage_execution_authorized"] = True
    assert "next_stage_execution_authorized" in mod.validate_card(card)

    card = mod.build_card()
    card["family_decisions"]["structured_policy_probe"]["status"] = "live"
    assert "family_status_not_inactive:structured_policy_probe" in mod.validate_card(card)
