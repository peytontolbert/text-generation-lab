import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12532_public_source_lane_expansion_and_train_support_admission_gate.py"
SUMMARY = ROOT / "runs/summaries/stage12532_public_source_lane_expansion_and_train_support_admission_gate.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12532_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12532_public_source_lane_gate_invariants():
    module = load_builder()
    module.main()
    summary = module.read_json(SUMMARY)

    assert summary["stage"] == "stage12532_public_source_lane_expansion_and_train_support_admission_gate"
    assert summary["training_allowed"] is False
    assert summary["countable_train_support"]["previous_countable_total_from_stage12417"] == 190
    assert summary["countable_train_support"]["new_countable_public_local_rows_from_stage12421"] == 2
    assert summary["countable_train_support"]["current_countable_total"] == 192
    assert summary["countable_train_support"]["remaining_gap_to_500"] == 308
    assert summary["baseline_countable_train_support_count"] == 190
    assert summary["new_countable_train_support_count"] == 2
    assert summary["countable_train_support_count"] == 192
    assert summary["remaining_gap_to_500"] == 308

    assert summary["required_buckets"] == {
        "fixture_curriculum_only": 64,
        "proof_candidate_only": 2,
        "train_support_only": 101,
    }
    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0
    assert summary["duplicate_train_row_count"] == 0
    assert summary["collapse_group_count"] == 13
    assert "legacy_train_support_collapse_groups_present" in summary["training_blockers"]
    assert summary["level3_admitted"] == 0
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["fail_to_pass_claim_admitted_rows"] == 0
    assert summary["proof_candidate_external_credit_count"] == 0
    assert summary["checks"]["fixture_rows_excluded_from_500"] is True
    assert summary["checks"]["proof_candidates_excluded_from_500"] is True
    assert summary["checks"]["zero_level3_patch_trace_repair_credit"] is True
