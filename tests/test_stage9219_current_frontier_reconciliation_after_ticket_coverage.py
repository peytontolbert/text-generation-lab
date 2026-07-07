from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9219_current_frontier_reconciliation_after_ticket_coverage.py"
    spec = importlib.util.spec_from_file_location("stage9219_frontier", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_covered_families_are_the_three_repo_local_modes():
    mod = _load()
    assert set(mod.COVERED_FAMILIES) == {
        "structured_policy_probe",
        "bounded_decoder_ce_probe",
        "denoise_repair_probe",
    }


def test_validate_card_rejects_open_execution_metric():
    mod = _load()
    card = {
        "checks": {
            "source_stage9218_passed": True,
            "source_matrix_passed": True,
            "all_expected_families_covered": True,
            "family_ticket_audits_passed": True,
            "blocked_items_recorded": True,
            "registry_frontier_stage9218": True,
            "authority_counts_zero": True,
        },
        "authority": dict(mod.AUTHORITY_CLOSED),
        "metrics": {
            "same_stage_execution_authorized": True,
            "next_stage_execution_authorized": False,
            "final_pre_execution_audit_authorized_now": False,
            "live_ticket_materialized_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "checkpoint_written_now": False,
            "cleanup_authorized_now": False,
            "runtime_authorized_flag": False,
            "runtime_verifier_execution_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
        },
    }
    failures = mod.validate_card(card, {"metrics": {"latest_stage": 9218}})
    assert "same_stage_execution_authorized" in failures


def test_blocked_until_explicit_request_includes_cleanup_and_arxiv():
    mod = _load()
    assert "cleanup" in mod.BLOCKED_UNTIL_EXPLICIT_REQUEST
    assert "arxiv_access_or_mining" in mod.BLOCKED_UNTIL_EXPLICIT_REQUEST
