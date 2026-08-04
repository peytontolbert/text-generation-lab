import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12624_count_source_reconciliation_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12624", SCRIPT)
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
        "stage12625_allowed", "vm_branch_active", "vm_runner_implementation_allowed", "vm_runner_implementation_ready",
        "vm_runner_execution_allowed", "vm_runner_evidence_present", "vm_runner_trustworthy", "storage_root_created",
        "storage_write_performed", "execution_performed", "replay_trustworthy", "raw_replay_evidence_present",
        "trusted_replay_raw_evidence_present", "causal_transition_atoms_present", "causal_transition_atoms_allowed",
        "level3_preflight_allowed", "level_3_materialized", "level_3_materialization_allowed",
        "training_admission_preflight_allowed", "training_admission_allowed", "training_admitted", "training_allowed",
        "training_run_allowed", "gpu_allocation_requested", "cuda2_training_allowed", "strict_eval_admitted",
        "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed",
        "ranking_allowed", "positive_stop", "authoritative_ledger_updated", "control_board_promoted_to_authoritative",
    ):
        assert field in record
        assert record[field] is False


def test_load_inputs_requires_scoped_stage12623_gate_and_pinned_sources():
    inputs = stage.load_inputs()
    s12623 = inputs["stage12623_summary"]
    sources = inputs["sources"]
    assert s12623["stage12624_count_source_reconciliation_preflight_only_allowed"] is True
    assert s12623["stage12624_allowed"] is False
    assert s12623["authoritative_planning_baseline_tasks"] == 158
    assert s12623["authoritative_training_gap_to_500"] == 342
    assert sources["stage12376"]["current_admitted_train_support_tasks"] == 158
    assert sources["stage12419"]["countable_train_support"]["stage12417_current_admitted_train_support_tasks"] == 190


def test_reconciliation_preflight_classifies_32_task_delta_without_admission():
    preflight = stage.build_reconciliation_preflight(stage.load_inputs())
    assert preflight["authoritative_baseline_stage"] == "stage12376_combined_train_support_ledger_v11"
    assert preflight["authoritative_admitted_train_support_tasks"] == 158
    assert preflight["authoritative_gap_to_500"] == 342
    assert preflight["control_board_advisory_countable_supply_tasks"] == 190
    assert preflight["control_board_advisory_gap_to_500"] == 310
    assert preflight["raw_delta_to_reconcile"] == 32
    assert preflight["stage12385_selected_lineage_delta"] == 14
    assert preflight["stage12416_direct_real_log_delta"] == 18
    assert preflight["stage12418_derived_projection_countable_rows"] == 0
    assert preflight["stage12418_derived_projection_rows_excluded"] == 292
    assert preflight["reconciliation_status"] == "not_reconciled_no_authoritative_ledger_update"
    assert preflight["preflight_only"] is True
    assert preflight["new_admission_performed"] is False
    assert preflight["training_allowed_after_preflight"] is False


def test_delta_components_require_review_and_have_dedupe_evidence():
    preflight = stage.build_reconciliation_preflight(stage.load_inputs())
    components = preflight["delta_components"]
    assert [component["component_id"] for component in components] == [
        "stage12385_minus_stage12376_selected_test_lineage_delta",
        "stage12416_direct_real_log_delta",
    ]
    assert [component["candidate_task_delta"] for component in components] == [14, 18]
    for component in components:
        assert component["candidate_status"] == "reconciliation_review_required_not_admitted"
        assert component["admission_action"] == "none_preflight_only"
        assert component["dedupe_keys"]
        assert component["evidence_to_verify"]
        assert component["exclusion_rules"]
    assert "do_not_count_stage12418_derived_projection_rows" in components[1]["exclusion_rules"]


def test_packet_keeps_all_admission_training_vm_and_broad_successor_gates_false():
    summary, contract, private = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "COUNT_SOURCE_RECONCILIATION_PREFLIGHT_RECORDED_NO_ADMISSION"
    assert summary["count_source_reconciliation_preflight_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12625_authoritative_ledger_reconciliation_review_only_allowed"] is True
    assert summary["stage12625_allowed"] is False
    assert summary["stage12624_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["control_board_promoted_to_authoritative"] is False
    assert summary["dataset_admission_allowed"] is False
    assert summary["new_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert contract["private_reconciliation_preflight_sha256"] == independent_stable_hash(private)
    assert summary["reconciliation_preflight_sha256"] == independent_stable_hash(private["reconciliation_preflight"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_reconciliation_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/count_source_reconciliation_preflight_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_preflight():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/count_source_reconciliation_preflight_only.json")
    assert summary == external
    assert summary["count_source_reconciliation_preflight_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12625_authoritative_ledger_reconciliation_review_only_allowed"] is True
    assert summary["stage12625_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["authoritative_admitted_train_support_tasks"] == 158
    assert summary["authoritative_gap_to_500"] == 342
    assert summary["control_board_advisory_countable_supply_tasks"] == 190
    assert summary["raw_delta_to_reconcile"] == 32
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_reconciliation_preflight_sha256"] == independent_stable_hash(private)
    assert pointer["reconciliation_preflight_sha256"] == independent_stable_hash(private["reconciliation_preflight"])
    assert summary["private_reconciliation_preflight_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/", "combined_selected_test_rows",
        "combined_train_support_rows", "direct_verifier_log_train_support_manifest",
    )
    allowed_true = {
        "count_source_reconciliation_preflight_only",
        "vm_branch_remains_paused",
        "stage12625_authoritative_ledger_reconciliation_review_only_allowed",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
