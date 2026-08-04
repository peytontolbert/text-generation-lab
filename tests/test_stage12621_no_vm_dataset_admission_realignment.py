import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12621_no_vm_dataset_admission_realignment.py"
SPEC = importlib.util.spec_from_file_location("stage12621", SCRIPT)
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
        "implementation_ready", "source_packet_implementation_allowed", "source_packet_executable",
        "stage12620_allowed", "stage12621_allowed", "stage12622_allowed", "vm_branch_active",
        "vm_runner_implementation_allowed", "vm_runner_implementation_ready", "vm_runner_execution_allowed",
        "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created", "storage_write_performed",
        "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_allowed",
        "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
        "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted",
        "training_allowed", "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "ranking_allowed", "positive_stop",
    ):
        assert field in record
        assert record[field] is False


def test_load_pinned_inputs_confirms_training_blocked_sources():
    inputs = stage.load_pinned_inputs()
    assert inputs["stage12376_summary"]["training_allowed"] is False
    assert inputs["stage12376_summary"]["current_admitted_train_support_tasks"] == 158
    assert inputs["stage12376_summary"]["remaining_gap_to_500"] == 342
    assert inputs["stage12419_summary"]["training_allowed"] is False
    assert "countable_supply_190" in inputs["stage12419_summary"]["decision"]
    assert inputs["stage12620_summary"]["stage12620_static_review_only_allowed"] is True
    assert inputs["stage12620_summary"]["training_allowed"] is False


def test_dataset_state_centers_scale_quality_not_vm():
    state = stage.extract_dataset_state(stage.load_pinned_inputs())
    assert state["authoritative_ledger_admitted_train_support_tasks"] == 158
    assert state["authoritative_ledger_target_train_support_tasks"] == 500
    assert state["authoritative_ledger_remaining_gap_to_500"] == 342
    assert state["control_board_countable_supply_tasks"] == 190
    assert state["strict_plus_audit_full_context_trainer_rows"] == 11
    assert state["strict_plus_audit_retrieval_rows"] == 729
    assert state["small_dry_run_possible_from_existing_bundle"] is True
    assert state["frontier_100m_training_dataset_ready"] is False
    assert state["global_training_allowed_by_authoritative_ledgers"] is False


def test_realignment_pauses_vm_and_keeps_training_execution_blocked():
    summary, contract, private = stage.build_realignment_packet(stage.load_pinned_inputs())
    assert summary["decision"] == "VM_BRANCH_PAUSED_DATASET_ADMISSION_SCALE_AND_QUALITY_CRITICAL_PATH"
    assert summary["vm_branch_paused"] is True
    assert summary["dataset_scale_quality_critical_path"] is True
    assert summary["stage12622_dataset_admission_census_only_allowed"] is True
    assert summary["stage12622_allowed"] is False
    assert summary["vm_branch_active"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["storage_write_performed"] is False
    assert summary["execution_performed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert summary["training_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert contract["private_no_vm_dataset_realignment_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_realignment_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/no_vm_dataset_admission_realignment.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_realignment():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/no_vm_dataset_admission_realignment.json")
    assert summary == external
    assert summary["vm_branch_paused"] is True
    assert summary["dataset_scale_quality_critical_path"] is True
    assert summary["stage12622_dataset_admission_census_only_allowed"] is True
    assert summary["stage12622_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_no_vm_dataset_realignment_sha256"] == independent_stable_hash(private)
    assert summary["private_no_vm_dataset_realignment_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leak_literals_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/",
    )
    allowed_true = {
        "vm_branch_paused",
        "dataset_scale_quality_critical_path",
        "stage12622_dataset_admission_census_only_allowed",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
