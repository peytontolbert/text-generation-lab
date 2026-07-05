from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.bounded_decoder_ce_package_gate_builder import build_row


def base_row(arg_type: str = "ARG_NAME") -> dict:
    return {
        "row_id": "source_row_1",
        "split": "train",
        "source_row_ref": {"source_stage": "test", "source_row_id_in_model_input": False},
        "corrupted_state": {
            "language": "python",
            "file_extension": "py",
            "context_group": "add_import_plan",
            "argument_signal": "identifier_argument_visible",
            "bounded_argument_features": {"argument_evidence_visible": True},
            "budget": {"decoder_budget_ok": False},
        },
        "clean_state": {"bounded_argument_type": arg_type},
        "gate_status": {
            "source_inventory_lineage": True,
            "source_provenance": True,
            "contamination_leakage_detector": True,
            "golden_locked_eval_suite": True,
            "drift_canary_regression_monitor": True,
            "cluster_slice_near_duplicate_detector": True,
            "dataset_junk_ood_ranker_v1": True,
            "schema_drift_detector": True,
        },
    }


def test_candidate_arg_still_keeps_decoder_ce_closed() -> None:
    out = build_row(base_row("ARG_NAME"))
    assert out["clean_state"]["ce_gate_decision"] == "CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT"
    assert out["clean_state"]["decoder_ce_eligible_now"] is False
    assert out["loss_mask"]["decoder_ce"] is False
    assert out["authority"]["decoder_ce_training_authorized_next"] is False
    assert "target_text_not_materialized" in out["hard_blockers"]


def test_retrieve_more_is_blocked_not_candidate() -> None:
    out = build_row(base_row("RETRIEVE_MORE"))
    assert out["clean_state"]["ce_gate_decision"] == "CE_BLOCK_RETRIEVE_MORE_BEFORE_DECODING"
    assert out["loss_mask"]["decoder_ce"] is False


def test_missing_gate_status_is_hard_blocker() -> None:
    row = base_row("ARG_CALL")
    row["gate_status"]["schema_drift_detector"] = False
    out = build_row(row)
    assert "missing_gate_status" in out["hard_blockers"]
