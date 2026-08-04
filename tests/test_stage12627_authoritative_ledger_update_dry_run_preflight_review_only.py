import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12627_authoritative_ledger_update_dry_run_preflight_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12627", SCRIPT)
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
        "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12628_allowed",
        "stage12627_authoritative_ledger_update_dry_run_only_allowed", "stage12628_authoritative_ledger_dry_run_authorization_review_allowed",
        "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
        "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
        "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
        "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
        "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed",
        "authoritative_ledger_dry_run_allowed", "control_board_promoted_to_authoritative", "control_board_promotion_allowed",
        "row_artifacts_written", "summary_artifact_written", "ledger_update_materialized", "candidate_ledger_materialized",
        "candidate_rows_materialized", "dry_run_candidate_artifacts_written", "dry_run_authorized", "dry_run_ready",
    ):
        assert field in record
        assert record[field] is False


def test_load_stage12626_requires_no_dry_run_authorization_and_next_review_marker():
    loaded = stage.load_stage12626()
    summary = loaded["summary"]
    update_plan = loaded["update_plan"]
    assert summary["stage12627_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12627_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_plan"] == 158
    assert summary["authoritative_gap_to_500_after_plan"] == 342
    assert update_plan["future_stage_requirements"]["minimum_next_review"] == "stage12627_authoritative_ledger_update_dry_run_preflight_review"
    assert independent_stable_hash(update_plan) == stage.EXPECTED_HASHES["stage12626_update_plan"]


def test_preflight_review_confirms_requirements_but_not_authorization():
    review = stage.build_preflight_review(stage.load_stage12626())
    assert review["review_scope"] == "dry_run_preflight_review_only"
    assert review["review_status"] == "preflight_requirements_complete_but_dry_run_not_authorized"
    assert review["dry_run_authorization_status"] == "not_authorized_by_stage12626_or_stage12627"
    assert review["authoritative_count_after_review"] == 158
    assert review["authoritative_gap_after_review"] == 342
    assert review["conditional_candidate_count_if_later_dry_run_and_update_authorized"] == 190
    assert review["reviewed_plan_delta_total"] == 32
    assert review["required_private_manifest_count"] == 3
    assert review["candidate_artifacts_written"] == 0
    assert review["summary_artifacts_updated"] == 0
    assert review["dry_run_preflight_review_only"] is True
    assert review["dry_run_performed"] is False
    assert review["authoritative_ledger_update_performed"] is False


def test_preflight_review_checks_are_all_passed_and_non_executing():
    review = stage.build_preflight_review(stage.load_stage12626())
    assert review["review_check_count"] == 6
    assert [check["check_id"] for check in review["review_checks"]] == [
        "predecessor_has_no_dry_run_authorization",
        "authoritative_counts_preserved",
        "future_candidate_counts_are_conditional",
        "private_manifest_requirements_present",
        "dry_run_must_be_candidate_only",
        "training_admission_stays_separate",
    ]
    assert all(check["status"] == "passed" for check in review["review_checks"])
    assert review["review_checks"][0]["dry_run_allowed"] is False
    assert review["review_checks"][4]["authoritative_replacement_allowed"] is False
    assert review["review_checks"][5]["training_allowed"] is False


def test_packet_keeps_all_dry_run_update_admission_training_vm_and_successor_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12626())
    assert summary["decision"] == "DRY_RUN_PREFLIGHT_REVIEW_RECORDED_NO_DRY_RUN_AUTHORIZATION"
    assert summary["dry_run_preflight_review_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["dry_run_authorization_status"] == "not_authorized_by_stage12626_or_stage12627"
    assert summary["stage12627_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12628_authoritative_ledger_dry_run_authorization_review_allowed"] is False
    assert summary["stage12627_allowed"] is False
    assert summary["stage12628_allowed"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["dry_run_ready"] is False
    assert summary["authoritative_ledger_dry_run_performed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["candidate_artifacts_written"] == 0
    assert summary["training_allowed"] is False
    assert contract["private_dry_run_preflight_review_sha256"] == independent_stable_hash(private)
    assert summary["dry_run_preflight_review_sha256"] == independent_stable_hash(private["dry_run_preflight_review"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_preflight_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_dry_run_preflight_review_only.json",
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
    private = read_json(out / "private/authoritative_ledger_dry_run_preflight_review_only.json")
    assert summary == external
    assert summary["dry_run_preflight_review_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12627_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12628_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert summary["authoritative_gap_to_500_after_review"] == 342
    assert summary["reviewed_plan_delta_total"] == 32
    assert summary["candidate_artifacts_written"] == 0
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_dry_run_preflight_review_sha256"] == independent_stable_hash(private)
    assert pointer["dry_run_preflight_review_sha256"] == independent_stable_hash(private["dry_run_preflight_review"])
    assert summary["private_dry_run_preflight_review_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
        "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
        "guardrail_scan.json", "combined_train_support_ledger", "jsonl", "row_id", "stable_lineage_key",
    )
    allowed_true = {
        "dry_run_preflight_review_only",
        "vm_branch_remains_paused",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
