import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12622_dataset_admission_census_only.py"
SPEC = importlib.util.spec_from_file_location("stage12622", SCRIPT)
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
        "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "stage12623_allowed",
        "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready",
        "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy",
        "storage_root_created", "storage_write_performed", "execution_performed", "replay_trustworthy",
        "raw_replay_evidence_present", "trusted_replay_raw_evidence_present", "causal_transition_atoms_present",
        "causal_transition_atoms_allowed", "level3_preflight_allowed", "level_3_materialized",
        "level_3_materialization_allowed", "training_admission_preflight_allowed", "training_admission_allowed",
        "training_admitted", "training_allowed", "training_run_allowed", "gpu_allocation_requested",
        "cuda2_training_allowed", "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible",
        "sealed_eval_eligible", "admission_allowed", "ranking_allowed", "positive_stop",
    ):
        assert field in record
        assert record[field] is False


def test_load_pinned_inputs_requires_stage12621_census_only_authorization():
    inputs = stage.load_pinned_inputs()
    s12621 = inputs["stage12621_summary"]
    assert s12621["decision"] == "VM_BRANCH_PAUSED_DATASET_ADMISSION_SCALE_AND_QUALITY_CRITICAL_PATH"
    assert s12621["stage12622_dataset_admission_census_only_allowed"] is True
    assert s12621["stage12622_allowed"] is False
    assert s12621["training_allowed"] is False
    assert s12621["vm_runner_execution_allowed"] is False


def test_census_counts_current_train_ready_supply_without_admission():
    census = stage.build_census(stage.load_pinned_inputs())
    assert census["selected_shard_count"] == 14
    assert census["training_ready_shard_count"] == 14
    assert census["strict_builder_shard_count"] == 10
    assert census["audit_only_direct_shard_count"] == 4
    assert census["manifest_ready_row_count"] == 14
    assert census["manifest_missing_required_outputs_count"] == 0
    assert census["manifest_acceptance_mode_counts"] == {"audit_only_direct": 4, "strict_builder": 10}
    assert census["manifest_pack_token_total"] == 69185759
    assert census["manifest_target_audit_count_total"] == 906
    assert census["full_context_trainer_rows"] == 11
    assert census["retrieval_rows"] == 729
    assert census["split_rows_total"] == 751
    assert census["sampled_manifest_rows_total"] == 751
    assert census["split_counts"] == {"eval": 126, "strict_eval": 36, "train": 589}
    assert census["sampled_manifest_split_counts"] == {"eval": 126, "strict_eval": 36, "train": 589}
    assert census["authoritative_ledger_admitted_train_support_tasks"] == 158
    assert census["authoritative_ledger_remaining_gap_to_500"] == 342
    assert census["stage12376_selected_test_rows_admitted_after_audit"] == 67
    assert census["stage12376_selected_test_rows_superseded_from_base"] == 3
    assert census["stage12376_selected_test_rows_quarantined_after_audit"] == 52
    assert census["control_board_countable_supply_tasks"] == 190
    assert census["control_board_remaining_gap_to_500"] == 310
    assert census["control_board_stage12385_baseline_tasks"] == 172
    assert census["control_board_net_new_direct_real_log_rows"] == 18
    assert census["derived_sanitized_projection_rows"] == 292
    assert census["derived_countable_as_new_train_support_rows"] == 0
    assert census["dataset_admission_manifest_dataset_count"] == 52
    assert census["dataset_admission_manifest_catalog_patch_candidate_count"] == 30
    assert census["dataset_admission_manifest_route_counts"] == {
        "EVAL_ONLY": 3,
        "PAPER_SUPPORT_ONLY": 22,
        "REJECT_GENERIC": 10,
        "REJECT_UNKNOWN": 12,
        "RETRIEVAL_AUX_ONLY": 3,
        "STRICT_TRACE_EPISODE_IMPORT": 1,
        "TRACE_SUPPORT_ONLY": 1,
    }
    assert census["new_admission_performed"] is False
    assert census["frontier_100m_training_dataset_ready"] is False
    assert census["vm_required_for_this_census"] is False


def test_census_packet_keeps_training_vm_and_broad_successor_gates_false():
    summary, contract, private = stage.build_census_packet(stage.load_pinned_inputs())
    assert summary["decision"] == "DATASET_ADMISSION_CENSUS_RECORDED_SCALE_GAP_REMAINS_BLOCKING"
    assert summary["dataset_admission_census_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12623_dataset_gap_plan_only_allowed"] is True
    assert summary["stage12623_allowed"] is False
    assert summary["dataset_admission_allowed"] is False
    assert summary["new_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert contract["private_dataset_admission_census_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_census_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/dataset_admission_census_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_census():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/dataset_admission_census_only.json")
    assert summary == external
    assert summary["dataset_admission_census_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12623_dataset_gap_plan_only_allowed"] is True
    assert summary["stage12623_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["split_rows_total"] == 751
    assert summary["split_train_rows"] == 589
    assert summary["split_eval_rows"] == 126
    assert summary["split_strict_eval_rows"] == 36
    assert summary["control_board_remaining_gap_to_500"] == 310
    assert summary["derived_sanitized_projection_rows"] == 292
    assert summary["dataset_admission_manifest_dataset_count"] == 52
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_dataset_admission_census_sha256"] == independent_stable_hash(private)
    assert summary["private_dataset_admission_census_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/",
    )
    allowed_true = {"dataset_admission_census_only", "vm_branch_remains_paused", "stage12623_dataset_gap_plan_only_allowed"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
