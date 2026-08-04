import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12639_curriculum_coverage_admission_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12639", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


def true_fields(record):
    return {key for key, value in record.items() if value is True}


ALLOWED_TRUE = {
    "authoritative_ledger_update_allowed",
    "authoritative_ledger_updated",
    "ledger_update_materialized",
    "stage12638_authoritative_ledger_update_materialization_only_allowed",
    "stage12639_curriculum_coverage_preflight_allowed",
    "stage12639_curriculum_coverage_preflight_only",
    "stage12639_curriculum_coverage_preflight_performed",
    "stage12640_canonical_curriculum_renderer_preflight_allowed",
    "vm_branch_remains_paused",
}


def test_load_stage12638_pins_materialization_and_rows():
    loaded = stage.load_stage12638()
    assert loaded["summary"]["authoritative_admitted_train_support_tasks_after_update"] == 190
    assert loaded["summary"]["stage12639_curriculum_coverage_preflight_allowed"] is True
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["rows"]) == 99


def test_row_audit_records_canonical_blockers_and_curriculum_support():
    loaded = stage.load_stage12638()
    schema = stage.load_schema()
    matrix, private_rows = stage.row_audit(loaded["rows"], schema)
    assert matrix["row_count"] == 99
    assert matrix["canonical_trainer_ready_rows"] == 0
    assert matrix["canonical_trainer_blocked_rows"] == 99
    assert matrix["row_local_training_allowed_metadata_count"] == 81
    assert matrix["missing_required_field_counts"]["split"] == 99
    assert matrix["missing_required_field_counts"]["input_state"] == 99
    assert matrix["missing_required_field_counts"]["target"] == 99
    assert matrix["unsupported_loss_key_counts"]["bounded_choice_aux"] == 81
    assert matrix["unsupported_loss_key_counts"]["structured_aux"] == 81
    assert matrix["unsupported_loss_key_counts"]["transition_projection"] == 81
    assert matrix["task_family_or_projection_counts"]["transition_next_action"] == 16
    assert matrix["task_family_or_projection_counts"]["transition_continue_or_stop"] == 25
    assert matrix["task_family_or_projection_counts"]["transition_verifier_transition"] == 25
    assert matrix["curriculum_signal_counts"]["continue_stop_policy"] == 25
    assert matrix["curriculum_signal_counts"]["verifier_transition_classification_partial"] == 25
    assert matrix["curriculum_signal_counts"]["direct_verifier_observation_partial"] == 18
    assert "repo_graph_candidates" in matrix["missing_curriculum_signals"]
    assert len(private_rows) == 99
    assert any(row["row_local_training_allowed_normalized_to_train_support_only"] for row in private_rows)


def test_preflight_keeps_admission_and_training_forbidden():
    loaded = stage.load_stage12638()
    matrix, _ = stage.row_audit(loaded["rows"], stage.load_schema())
    preflight = stage.build_preflight(loaded, matrix)
    assert preflight["preflight_scope"] == "curriculum_coverage_admission_preflight_only"
    assert preflight["authoritative_train_support_tasks_after_update"] == 190
    assert preflight["canonical_trainer_ready_rows"] == 0
    assert preflight["dataset_rows_admitted_after_preflight"] is False
    assert preflight["training_allowed_after_preflight"] is False
    assert preflight["recommended_next_stage"] == "stage12640_canonical_curriculum_renderer_preflight_only"


def test_public_private_contract_only_sets_scoped_true_gates():
    summary, contract, private, matrix, private_rows = stage.build_packet(stage.load_stage12638(), stage.load_schema())
    assert summary["decision"] == "CURRICULUM_COVERAGE_PREFLIGHT_RECORDED_NO_ADMISSION_OR_TRAINING"
    assert summary["canonical_trainer_ready_rows"] == 0
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert true_fields(summary) == ALLOWED_TRUE
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE | {"private_row_audit_sha256_pending_external_file"}
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    assert contract["curriculum_coverage_matrix_sha256"] == stable(matrix)
    assert len(private_rows) == 99


def test_build_writes_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "curriculum_coverage_matrix.json",
        "digest_pointer.json",
        "private/curriculum_coverage_admission_preflight_only.json",
        "private/row_curriculum_audit.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert sum(1 for _ in (out / "private/row_curriculum_audit.jsonl").open()) == 99


def test_generated_artifacts_match_current_preflight():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/curriculum_coverage_admission_preflight_only.json")
    matrix = read_json(out / "curriculum_coverage_matrix.json")
    assert summary == external
    assert summary["authoritative_admitted_train_support_tasks_after_update"] == 190
    assert summary["canonical_trainer_ready_rows"] == 0
    assert summary["next_required_action"] == "stage12640_canonical_curriculum_renderer_preflight_only"
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_curriculum_coverage_preflight_sha256"] == stable(private)
    assert pointer["curriculum_coverage_matrix_sha256"] == stable(matrix)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_no_training_authority():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json", stage.OUT / "curriculum_coverage_matrix.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("level_3_materialized") is not True
