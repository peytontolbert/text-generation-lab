import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12623_dataset_gap_plan_only.py"
SPEC = importlib.util.spec_from_file_location("stage12623", SCRIPT)
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


def test_load_stage12622_requires_gap_plan_only_gate():
    loaded = stage.load_stage12622()
    summary = loaded["summary"]
    assert summary["decision"] == "DATASET_ADMISSION_CENSUS_RECORDED_SCALE_GAP_REMAINS_BLOCKING"
    assert summary["stage12623_dataset_gap_plan_only_allowed"] is True
    assert summary["stage12623_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["control_board_countable_supply_tasks"] == 190
    assert summary["authoritative_ledger_admitted_train_support_tasks"] == 158


def test_gap_plan_keeps_158_and_190_counts_explicit():
    plan = stage.build_gap_plan(stage.load_stage12622()["summary"])
    assert plan["planning_baseline"] == "stage12376_authoritative_ledger_158"
    assert plan["authoritative_ledger_baseline_preserved"] == "stage12376_158_admitted_train_support_tasks"
    assert plan["authoritative_training_gap_to_500"] == 342
    assert plan["authoritative_ledger_gap_to_500"] == 342
    assert plan["control_board_advisory_countable_supply_tasks"] == 190
    assert plan["control_board_advisory_gap_to_500"] == 310
    assert plan["count_source_delta_to_reconcile"] == 32
    assert plan["current_compiled_trainer_rows"] == 11
    assert plan["current_split_train_rows"] == 589
    assert plan["catalog_patch_candidate_count"] == 30
    assert plan["dataset_route_counts"]["PAPER_SUPPORT_ONLY"] == 22
    assert plan["dataset_route_counts"]["STRICT_TRACE_EPISODE_IMPORT"] == 1
    assert plan["derived_countable_as_new_train_support_rows"] == 0
    assert plan["plan_only"] is True
    assert plan["new_admission_performed"] is False
    assert plan["training_allowed_after_plan"] is False
    assert len(plan["candidate_worklist"]) == 3
    for candidate in plan["candidate_worklist"]:
        assert candidate["admission_status"] == "not_admitted"
        assert candidate["dedupe_keys"]
        assert candidate["exclusion_rules"]
        assert candidate["required_admission_evidence"]
        assert "control_board_reconciliation" in candidate


def test_gap_plan_waves_are_reviews_not_admissions():
    plan = stage.build_gap_plan(stage.load_stage12622()["summary"])
    waves = plan["planning_waves"]
    assert [wave["wave"] for wave in waves] == [
        "A_reconcile_count_sources",
        "B_strict_trace_import_adapter",
        "C_catalog_patch_candidate_triage",
        "D_paper_support_to_grounded_tasks",
        "E_retrieval_aux_preserve_as_auxiliary",
    ]
    assert [wave["successor_review_required"] for wave in waves] == [
        "source_count_reconciliation_review",
        "strict_adapter_materialization_preflight",
        "per_candidate_source_and_quality_review",
        "non_repair_train_support_policy_review",
        "retrieval_aux_policy_review_if_needed",
    ]
    for wave in waves:
        assert wave["admission_action"].endswith("plan_only")
        assert "successor_review_required" in wave
    assert waves[0]["target_delta_tasks"] == 32
    assert waves[2]["candidate_count"] == 30


def test_gap_plan_packet_keeps_training_vm_and_broad_successor_gates_false():
    summary, contract, private = stage.build_gap_plan_packet(stage.load_stage12622())
    assert summary["decision"] == "DATASET_GAP_PLAN_RECORDED_NO_ADMISSION_OR_TRAINING"
    assert summary["dataset_gap_plan_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12624_count_source_reconciliation_preflight_only_allowed"] is True
    assert summary["stage12624_allowed"] is False
    assert summary["dataset_admission_allowed"] is False
    assert summary["new_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["replay_trustworthy"] is False
    assert summary["level_3_materialized"] is False
    assert contract["private_dataset_gap_plan_sha256"] == independent_stable_hash(private)
    assert summary["dataset_gap_plan_sha256"] == independent_stable_hash(private["gap_plan"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_gap_plan_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/dataset_gap_plan_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_gap_plan():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/dataset_gap_plan_only.json")
    assert summary == external
    assert summary["dataset_gap_plan_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["stage12624_count_source_reconciliation_preflight_only_allowed"] is True
    assert summary["stage12624_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["frontier_100m_training_dataset_ready"] is False
    assert summary["authoritative_planning_baseline_tasks"] == 158
    assert summary["control_board_advisory_countable_supply_tasks"] == 190
    assert summary["authoritative_training_gap_to_500"] == 342
    assert summary["control_board_advisory_gap_to_500"] == 310
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_dataset_gap_plan_sha256"] == independent_stable_hash(private)
    assert summary["private_dataset_gap_plan_sha256"] == independent_stable_hash(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    forbidden = (
        "/data/", "/arxiv/", "agentkernel_vm_replay", "/dev/", "selector", "raw_stream",
        "stdout.raw", "stderr.raw", "before_commit_oid", "after_commit_oid", "production_path",
        "production_patch_sha256", "manual_executor_slot_contracts", "slot_1.patch", "slot_2.patch",
        "repository_root", "patch_path", "slot_1/", "slot_2/",
    )
    allowed_true = {
        "dataset_gap_plan_only",
        "vm_branch_remains_paused",
        "stage12624_count_source_reconciliation_preflight_only_allowed",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in forbidden if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
