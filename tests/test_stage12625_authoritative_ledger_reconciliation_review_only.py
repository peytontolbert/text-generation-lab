import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12625_authoritative_ledger_reconciliation_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12625", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def independent_stable_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def assert_false_boundaries(record):
    for field in (
        "implementation_ready", "dataset_admission_allowed", "dataset_rows_admitted", "new_rows_admitted",
        "frontier_100m_training_dataset_ready", "source_packet_implementation_allowed", "source_packet_executable",
        "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed", "stage12624_allowed",
        "stage12625_allowed", "stage12626_allowed", "vm_branch_active", "vm_runner_implementation_allowed",
        "vm_runner_implementation_ready", "vm_runner_execution_allowed", "vm_runner_evidence_present",
        "vm_runner_trustworthy", "storage_root_created", "storage_write_performed", "execution_performed",
        "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
        "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
        "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
        "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "control_board_promoted_to_authoritative",
        "control_board_promotion_allowed",
    ):
        assert field in record
        assert record[field] is False


def test_load_inputs_requires_scoped_stage12624_gate_and_pinned_evidence():
    inputs = stage.load_inputs()
    s12624 = inputs["stage12624_summary"]
    assert s12624["stage12625_authoritative_ledger_reconciliation_review_only_allowed"] is True
    assert s12624["stage12625_allowed"] is False
    assert s12624["authoritative_admitted_train_support_tasks"] == 158
    assert s12624["authoritative_gap_to_500"] == 342
    assert s12624["raw_delta_to_reconcile"] == 32
    assert inputs["row_hashes"]["stage12385_rows"] == stage.EXPECTED_HASHES["stage12385_rows"]
    assert inputs["row_hashes"]["stage12416_rows"] == stage.EXPECTED_HASHES["stage12416_rows"]


def test_review_records_supersession_arithmetic_for_selected_lineage_delta():
    review = stage.build_review(stage.load_inputs())
    component = review["review_components"][0]
    assert component["component_id"] == "stage12385_minus_stage12376_selected_test_lineage_delta"
    assert component["review_status"] == "passed_for_later_authoritative_ledger_update_plan_not_admitted"
    assert component["net_task_delta"] == 14
    assert component["selected_rows_before"] == 67
    assert component["selected_rows_after"] == 81
    assert component["row_ids_added"] == 30
    assert component["row_ids_removed_or_superseded"] == 6
    assert component["prior_duplicate_extra_rows_removed"] == 10
    assert component["post_review_duplicate_extra_rows"] == 0
    assert component["risk_counts"] == {"risky_claim_rows": 0, "raw_source_or_log_rows": 0}


def test_review_records_direct_log_delta_guardrails_without_level3_or_repair_claims():
    review = stage.build_review(stage.load_inputs())
    component = review["review_components"][1]
    assert component["component_id"] == "stage12416_direct_real_log_delta"
    assert component["review_status"] == "passed_for_later_authoritative_ledger_update_plan_not_admitted"
    assert component["net_task_delta"] == 18
    assert component["direct_log_projection_rows"] == 18
    assert component["rows_present_in_stage12417"] == 18
    assert component["post_review_duplicate_extra_rows"] == 0
    assert component["guardrail_scan_passed"] is True
    assert component["risk_counts"] == {"risky_claim_rows": 0, "raw_leak_rows": 0, "overclaim_rows": 0}


def test_review_packet_keeps_authoritative_count_unchanged_and_all_broad_gates_false():
    summary, contract, private = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "AUTHORITATIVE_LEDGER_RECONCILIATION_REVIEW_PASSED_UPDATE_PLAN_REQUIRED_NO_ADMISSION"
    assert summary["authoritative_ledger_reconciliation_review_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12626_authoritative_ledger_update_plan_only_allowed"] is True
    assert summary["stage12626_allowed"] is False
    assert summary["stage12625_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["authoritative_ledger_update_allowed"] is False
    assert summary["control_board_promoted_to_authoritative"] is False
    assert summary["dataset_admission_allowed"] is False
    assert summary["new_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert summary["authoritative_gap_to_500_after_review"] == 342
    assert summary["candidate_count_after_future_update_if_authorized"] == 190
    assert contract["private_reconciliation_review_sha256"] == independent_stable_hash(private)
    assert summary["reconciliation_review_sha256"] == independent_stable_hash(private["reconciliation_review"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_reconciliation_review_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_review():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_reconciliation_review_only.json")
    assert summary == external
    assert summary["authoritative_ledger_reconciliation_review_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12626_authoritative_ledger_update_plan_only_allowed"] is True
    assert summary["stage12626_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["reviewed_delta_total"] == 32
    assert summary["review_passed_delta_total"] == 32
    assert summary["review_blocked_delta_total"] == 0
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_reconciliation_review_sha256"] == independent_stable_hash(private)
    assert pointer["reconciliation_review_sha256"] == independent_stable_hash(private["reconciliation_review"])
    assert summary["private_reconciliation_review_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
        "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
        "guardrail_scan.json",
    )
    allowed_true = {
        "authoritative_ledger_reconciliation_review_only",
        "vm_branch_remains_paused",
        "stage12626_authoritative_ledger_update_plan_only_allowed",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
