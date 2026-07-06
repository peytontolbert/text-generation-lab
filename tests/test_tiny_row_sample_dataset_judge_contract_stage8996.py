from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8996_tiny_row_sample_dataset_judge_contract import (  # noqa: E402
    ACCEPT_ROUTES,
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    JUDGE_CRITERIA,
    JUDGE_OUTPUTS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8996_records_required_dataset_judge_criteria() -> None:
    card = build_contract(registry())
    assert "contamination_leakage_detector_pass" in JUDGE_CRITERIA
    assert "golden_locked_eval_suite_excluded" in JUDGE_CRITERIA
    assert "dataset_junk_ood_ranker_pass" in JUDGE_CRITERIA
    assert "loss_mask_candidates_explicit" in JUDGE_CRITERIA
    assert "no_target_leakage_in_model_visible_fields" in JUDGE_CRITERIA
    assert "judge_to_compiler_gate_status.json" in JUDGE_OUTPUTS
    assert card["metrics"]["judge_criteria"] >= 13


def test_stage8996_keeps_judging_manifest_and_training_closed() -> None:
    card = build_contract(registry())
    assert "DATASET_ROW_JUDGE_EXECUTION_NOW" in FORBIDDEN_OPERATIONS
    assert "EMIT_TRAINING_MANIFEST" in FORBIDDEN_OPERATIONS
    assert "START_TRAINING" in FORBIDDEN_OPERATIONS
    assert "ACCEPT_PENDING_LOCKED_MANIFEST_COMPILE" in ACCEPT_ROUTES
    assert card["metrics"]["dataset_judge_executed_now"] is False
    assert card["metrics"]["training_manifest_emitted"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8996_validation_rejects_open_authority_or_missing_safety_criterion() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["training_manifest_emitted"] = True
    assert "training_manifest_emitted" in validate_contract(unsafe)
    missing = build_contract(registry())
    missing["judge_criteria"] = [item for item in missing["judge_criteria"] if item != "dataset_junk_ood_ranker_pass"]
    assert "missing_criterion:dataset_junk_ood_ranker_pass" in validate_contract(missing)
