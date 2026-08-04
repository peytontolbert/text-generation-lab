import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12626_authoritative_ledger_update_plan_only.py"
SPEC = importlib.util.spec_from_file_location("stage12626", SCRIPT)
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
        "stage12625_allowed", "stage12626_allowed", "stage12627_allowed", "stage12627_authoritative_ledger_update_dry_run_only_allowed", "vm_branch_active",
        "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
        "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present", "trusted_replay_raw_evidence_present",
        "causal_transition_atoms_present", "causal_transition_atoms_allowed", "level3_preflight_allowed",
        "level_3_materialized", "level_3_materialization_allowed", "training_admission_preflight_allowed",
        "training_admission_allowed", "training_admitted", "training_allowed", "training_run_allowed",
        "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
        "authoritative_ledger_updated", "authoritative_ledger_update_allowed", "authoritative_ledger_dry_run_performed",
        "control_board_promoted_to_authoritative", "control_board_promotion_allowed", "row_artifacts_written",
        "summary_artifact_written", "ledger_update_materialized",
    ):
        assert field in record
        assert record[field] is False


def test_load_stage12625_requires_scoped_plan_gate_and_reviewed_delta():
    loaded = stage.load_stage12625()
    summary = loaded["summary"]
    private = loaded["private"]
    assert summary["stage12626_authoritative_ledger_update_plan_only_allowed"] is True
    assert summary["stage12626_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert summary["authoritative_gap_to_500_after_review"] == 342
    assert summary["review_passed_delta_total"] == 32
    assert private["reconciliation_review"]["authoritative_ledger_update_performed"] is False


def test_update_plan_records_future_mechanics_without_writes():
    plan = stage.build_update_plan(stage.load_stage12625())
    assert plan["plan_scope"] == "authoritative_ledger_update_plan_only"
    assert plan["authoritative_ledger_update_plan_only"] is True
    assert plan["authoritative_ledger_update_performed"] is False
    assert plan["new_admission_performed"] is False
    assert plan["training_allowed_after_plan"] is False
    assert plan["update_plan_step_count"] == 5
    assert [step["step_id"] for step in plan["update_plan_steps"]] == [
        "pin_authoritative_baseline",
        "apply_selected_lineage_supersession_plan",
        "append_direct_real_log_projection_plan",
        "dry_run_merged_ledger_plan",
        "publish_future_update_manifest_plan",
    ]
    for step in plan["update_plan_steps"]:
        assert step["writes_allowed_in_stage12626"] is False


def test_update_plan_preserves_counts_and_planned_deltas():
    plan = stage.build_update_plan(stage.load_stage12625())
    invariants = plan["invariants"]
    assert invariants["authoritative_count_before_stage12626"] == 158
    assert invariants["authoritative_gap_before_stage12626"] == 342
    assert invariants["authoritative_count_after_stage12626"] == 158
    assert invariants["authoritative_gap_after_stage12626"] == 342
    assert invariants["planned_candidate_count_after_later_update"] == 190
    assert invariants["planned_candidate_gap_after_later_update"] == 310
    assert invariants["planned_delta_total"] == 32
    assert invariants["stage12418_countable_rows"] == 0
    assert invariants["row_artifacts_to_write_now"] == 0
    assert invariants["summary_artifacts_to_update_now"] == 0
    assert [component["planned_delta"] for component in plan["planned_update_components"]] == [14, 18]
    assert plan["planned_update_components"][0]["materialization_status"] == "not_materialized_plan_only"
    assert plan["planned_update_components"][1]["materialization_status"] == "not_materialized_plan_only"


def test_update_plan_requires_private_manifests_for_later_dry_run():
    plan = stage.build_update_plan(stage.load_stage12625())
    requirements = plan["private_manifest_requirements"]
    supersession = requirements["supersession_manifest"]
    assert supersession["required"] is True
    assert supersession["source_transition"] == "stage12376_to_stage12385"
    assert supersession["row_ids_added"] == 30
    assert supersession["row_ids_removed_or_superseded"] == 6
    assert supersession["prior_duplicate_extra_rows_removed"] == 10
    assert supersession["net_delta"] == 14
    assert supersession["required_row_actions"] == ["keep", "add", "supersede", "drop_duplicate"]
    assert supersession["publicly_emitted"] is False
    direct = requirements["direct_log_merge_manifest"]
    assert direct["direct_log_projection_rows"] == 18
    assert direct["all_rows_must_be_present_in_stage12417"] is True
    assert "level3" in direct["forbidden_claims"]
    duplicate = requirements["duplicate_policy_manifest"]
    assert duplicate["post_update_duplicate_extra_rows_required"] == 0
    assert plan["future_stage_requirements"]["dry_run_must_materialize_private_manifest_requirements"] is True
    assert plan["future_stage_requirements"]["minimum_next_review"] == "stage12627_authoritative_ledger_update_dry_run_preflight_review"


def test_packet_keeps_all_admission_update_training_vm_and_broad_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12625())
    assert summary["decision"] == "AUTHORITATIVE_LEDGER_UPDATE_PLAN_RECORDED_NO_LEDGER_UPDATE_OR_ADMISSION"
    assert summary["authoritative_ledger_update_plan_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12627_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12627_allowed"] is False
    assert summary["stage12626_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["authoritative_ledger_update_allowed"] is False
    assert summary["authoritative_ledger_dry_run_performed"] is False
    assert summary["row_artifacts_written"] is False
    assert summary["summary_artifact_written"] is False
    assert summary["dataset_admission_allowed"] is False
    assert summary["new_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["planned_candidate_count_after_later_update"] == 190
    assert contract["private_update_plan_sha256"] == independent_stable_hash(private)
    assert summary["update_plan_sha256"] == independent_stable_hash(private["update_plan"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_plan_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_update_plan_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_plan():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_update_plan_only.json")
    assert summary == external
    assert summary["authoritative_ledger_update_plan_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12627_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12627_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_plan"] == 158
    assert summary["authoritative_gap_to_500_after_plan"] == 342
    assert summary["planned_delta_total"] == 32
    assert summary["row_artifacts_to_write_now"] == 0
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_update_plan_sha256"] == independent_stable_hash(private)
    assert pointer["update_plan_sha256"] == independent_stable_hash(private["update_plan"])
    assert summary["private_update_plan_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
        "combined_train_support_rows", "direct_verifier_log_train_support_manifest", "direct_verifier_log_train_support_rows",
        "guardrail_scan.json", "combined_train_support_ledger", "jsonl",
    )
    allowed_true = {
        "authoritative_ledger_update_plan_only",
        "vm_branch_remains_paused",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
