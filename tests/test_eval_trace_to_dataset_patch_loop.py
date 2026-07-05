from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from eval_trace_to_dataset_patch_loop import compile_trace, compile_traces


def test_compile_missing_evidence_to_counterfactual_patch() -> None:
    patch = compile_trace({"trace_id": "t1", "failure_type": "missing_evidence", "slice_tags": ["retrieval"]})
    assert patch["route"] == "PROPOSE_DATASET_PATCH"
    assert patch["dataset_op"] == "add_counterfactual"
    assert patch["recommended_action"] == "add_retrieval_counterfactuals"


def test_compile_symbol_failure_to_add_examples() -> None:
    patch = compile_trace({"eval_id": "e1", "failure_type": "symbol_resolution_failure"})
    assert patch["dataset_op"] == "add"
    assert patch["recommended_action"] == "add_symbol_binding_examples"


def test_compile_overbroad_patch_to_preference_pair() -> None:
    patch = compile_trace({"trace_id": "t2", "failure_type": "overbroad_patch"})
    assert patch["dataset_op"] == "add_preference_pair"


def test_blocks_locked_eval_trace() -> None:
    patch = compile_trace({"trace_id": "locked", "failure_type": "bad_label", "locked_eval_trace": True})
    assert patch["route"] == "BLOCK_DATASET_PATCH"
    assert "locked_or_hidden_eval_trace_forbidden_for_training_patch" in patch["blocked_reasons"]


def test_blocks_trace_with_target_answer() -> None:
    patch = compile_trace({"trace_id": "target", "failure_type": "decoder_invalid", "contains_target_answer": True})
    assert patch["blocked"] is True
    assert "trace_contains_target_answer" in patch["blocked_reasons"]


def test_compile_traces_counts_ops() -> None:
    card = compile_traces([
        {"trace_id": "a", "failure_type": "missing_evidence"},
        {"trace_id": "b", "failure_type": "flaky_failure"},
        {"trace_id": "c", "failure_type": "bad_label", "hidden_final_trace": True},
    ])
    assert card["metrics"]["proposed_patches"] == 2
    assert card["metrics"]["blocked_patches"] == 1
    assert card["metrics"]["op_counts"]["holdout"] == 1
