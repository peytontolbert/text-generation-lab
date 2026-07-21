import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12536_stage12535_semantic_risk_audit.py"
SUMMARY = ROOT / "runs/summaries/stage12536_stage12535_semantic_risk_audit.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12536_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12536_blocks_stage12535_metadata_inventory_rows():
    module = load_builder()
    summary = module.build()

    assert summary["stage"] == "stage12536_stage12535_semantic_risk_audit"
    assert summary["decision"] == "stage12535_blocked_demoted_semantically_weak_metadata_inventory"
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"] is False
    assert summary["countable_train_support_count"] == 0
    assert summary["new_countable_train_support_count"] == 0
    assert summary["semantic_grounding"]["semantically_grounded"] is False
    assert summary["semantic_grounding"]["metadata_only_source_signal"] is True
    assert summary["semantic_grounding"]["deterministic_label_rotation_signal"] is True
    assert summary["semantic_grounding"]["row_count"] == 373
    assert summary["semantic_grounding"]["rows_with_command_output_observation"] == 0
    assert summary["semantic_grounding"]["rows_missing_command_output_observation"] == 373
    assert summary["demotion"]["stage12535_rows_demoted_from_training_claims"] is True
    assert summary["demotion"]["blocked_row_count"] == 373
    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["strict_eval_eligible_count"] == 0
    assert summary["source_heldout_admissible_count"] == 0
    assert summary["gemma_or_product_claims"] == 0

    blockers = set(summary["training_blockers"])
    assert "stage12535_declares_public_local_repo_metadata_hash_only_source" in blockers
    assert "stage12535_rows_lack_real_command_output_observation_hashes" in blockers
    assert "stage12535_target_labels_match_deterministic_rotation_pattern" in blockers
    assert "separate_semantic_review_not_passed" in blockers


def test_stage12536_demoted_rows_are_hash_class_only_and_claim_free():
    module = load_builder()
    module.build()
    rows = module.read_jsonl(ROOT / "runs/local/artifacts/stage12536_stage12535_semantic_risk_audit/stage12535_demoted_semantic_risk_rows.jsonl")

    assert len(rows) == 373
    for row in rows[:10]:
        assert row["semantic_admission"] == "blocked_demoted_metadata_inventory_only"
        assert row["training_allowed"] is False
        assert row["countable_train_support"] is False
        assert row["level3_admitted"] is False
        assert row["patch_trace_admitted"] is False
        assert row["repair_claim_admitted"] is False
        assert row["strict_eval_eligible"] is False
        assert row["source_heldout_admissible"] is False
        assert "no_command_output_verifier_observation_present" in row["blocked_reasons"]


def test_stage12536_grounded_detector_requires_command_output_evidence():
    module = load_builder()
    row = {
        "source_stage": "fixture",
        "source_line_hash": "a" * 24,
        "root_lineage_key_hash": "b" * 24,
        "repo_family_hash": "c" * 24,
        "language_family": "python",
        "task_projection": "transition_verifier_transition",
        "target_semantic_value": "PASS_CURRENT_STATE",
        "verifier_status": "PASS_CURRENT_STATE",
        "verifier_command_ref_hash": "d" * 24,
        "verifier_exit_status_class": "exit_zero",
        "verifier_output_hash": "e" * 24,
        "training_allowed": False,
    }
    audit = module.semantic_grounding_audit([row], {"record_type": "grounded"}, {"source_policy": "command_output_hash_only"})

    assert audit["semantically_grounded"] is True
    assert audit["rows_with_command_output_observation"] == 1
    assert audit["weak_reasons"] == []
