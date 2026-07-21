import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12533_legacy_collapse_group_countable_repair.py"
SUMMARY = ROOT / "runs/summaries/stage12533_legacy_collapse_group_countable_repair.json"


def load_builder():
    spec = importlib.util.spec_from_file_location("stage12533_builder", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_stage12533_demotes_legacy_collapse_groups_without_training_credit():
    module = load_builder()
    module.main()
    summary = module.read_json(SUMMARY)

    assert summary["stage"] == "stage12533_legacy_collapse_group_countable_repair"
    assert summary["training_allowed"] is False
    assert summary["collapse_groups_from_stage12532"] == 13
    assert summary["demoted_legacy_collapse_rows"] == 65
    assert summary["demoted_collapsed_row_count"] == 65
    assert summary["demoted_countable_train_support_rows"] == 65
    assert summary["previous_countable_train_support_count"] == 192
    assert summary["pre_repair_collapse_group_count"] == 13
    assert summary["post_repair_collapse_group_count"] == 0
    assert summary["post_repair_countable_train_support_count"] == 127
    assert summary["public_local_exact_replacement_candidates"] == 0
    assert summary["replacement_candidate_count"] == 0
    assert summary["admissible_public_local_exact_replacement_candidates"] == 0
    assert summary["admitted_additional_train_support_rows"] == 0
    assert summary["countable_train_support"]["stage12532_countable_total"] == 192
    assert summary["countable_train_support"]["current_countable_total"] == 127
    assert summary["remaining_gap_to_500"] == 373
    assert summary["checks"]["legacy_collapse_countable_rows_demoted"] is True
    assert summary["checks"]["no_remaining_countable_train_collapse_groups"] is True
    assert summary["guardrail_scan_passed"] is True
    assert summary["raw_leak_count"] == 0
    assert summary["level3_admitted_rows"] == 0
    assert summary["patch_trace_admitted_rows"] == 0
    assert summary["patch_trace_rows"] == 0
    assert summary["repair_claim_admitted_rows"] == 0
    assert summary["fail_to_pass_claim_admitted_rows"] == 0
    assert summary["strict_eval_eligible_count"] == 0
    assert summary["source_heldout_admissible_count"] == 0
    assert "500_countable_train_support_floor_not_reached" in summary["training_blockers"]
    assert "no_exact_public_local_replacements_for_demoted_legacy_collapse_groups" in summary["training_blockers"]
