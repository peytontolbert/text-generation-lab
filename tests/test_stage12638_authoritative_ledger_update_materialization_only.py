import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12638_authoritative_ledger_update_materialization_only.py"
SPEC = importlib.util.spec_from_file_location("stage12638", SCRIPT)
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
    "authoritative_ledger_update_materialization_only",
    "authoritative_ledger_update_allowed",
    "authoritative_ledger_updated",
    "ledger_update_materialized",
    "row_artifacts_written",
    "summary_artifact_written",
    "storage_write_performed",
    "stage12638_authoritative_ledger_update_materialization_only_allowed",
    "stage12639_curriculum_coverage_preflight_allowed",
    "dry_run_authorization_granted",
    "dry_run_authorized",
    "authoritative_ledger_dry_run_allowed",
    "authoritative_ledger_dry_run_performed",
    "authoritative_ledger_update_dry_run_materialized",
    "candidate_ledger_materialized",
    "candidate_rows_materialized",
    "candidate_projection_rows_materialized",
    "dry_run_candidate_artifacts_written",
    "vm_branch_remains_paused",
}


def test_load_stage12637_requires_authorized_update_only():
    loaded = stage.load_stage12637()
    summary = loaded["summary"]
    authorization = loaded["authorization"]
    assert stable(authorization) == stage.EXPECTED_HASHES["stage12637_authorization"]
    assert authorization["authorization_scope"] == "authoritative_ledger_update_only"
    assert authorization["authorized_next_stage"] == stage.STAGE
    assert authorization["authorized_authoritative_count_after_update"] == 190
    assert summary["authoritative_ledger_update_allowed"] is True
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False


def test_load_candidate_rows_pins_rows_manifest_and_counts():
    loaded = stage.load_candidate_rows()
    assert len(loaded["rows"]) == 99
    assert stable(loaded["manifest"]) == stage.EXPECTED_HASHES["stage12635_candidate_manifest"]
    assert hashlib.sha256(loaded["rows_bytes"]).hexdigest() == stage.EXPECTED_HASHES["stage12635_rows_bytes"]
    manifest = loaded["manifest"]
    assert manifest["candidate_total_count_after_dry_run"] == 190
    assert manifest["candidate_delta_total"] == 32
    assert manifest["duplicate_row_ids_should_be_zero"] == 0
    assert manifest["raw_leak_count"] == 0
    assert manifest["overclaim_count"] == 0


def test_update_materializes_authoritative_count_but_not_admission_or_training():
    update, coverage = stage.build_update(stage.load_stage12637(), stage.load_candidate_rows())
    assert update["materialization_scope"] == "authoritative_ledger_update_materialization_only"
    assert update["authoritative_count_before_update"] == 158
    assert update["authoritative_count_after_update"] == 190
    assert update["authoritative_gap_after_update"] == 310
    assert update["authoritative_ledger_updated"] is True
    assert update["ledger_update_materialized"] is True
    assert update["dataset_rows_admitted"] is False
    assert update["new_admission_performed"] is False
    assert update["training_allowed_after_update"] is False
    assert update["level3_materialized_after_update"] is False
    assert coverage["next_preflight"] == "stage12639_curriculum_coverage_admission_preflight_only"
    assert "repo_graph_candidates" in coverage["missing_curriculum_signals"]


def test_public_private_contract_keeps_only_scoped_true_gates():
    summary, contract, private, coverage = stage.build_packet(stage.load_stage12637(), stage.load_candidate_rows())
    assert summary["decision"] == "AUTHORITATIVE_LEDGER_UPDATE_MATERIALIZED_NO_ADMISSION_OR_TRAINING"
    assert summary["authoritative_admitted_train_support_tasks_after_update"] == 190
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert true_fields(summary) == ALLOWED_TRUE | {"curriculum_coverage_preview_recorded"}
    assert true_fields(contract) == ALLOWED_TRUE
    assert true_fields(private) == ALLOWED_TRUE
    for record in (summary, contract, private):
        assert_false_boundaries(record)
    assert contract["private_authoritative_ledger_update_materialization_sha256"] == stable(private)
    assert contract["curriculum_coverage_preview_sha256"] == stable(coverage)


def test_build_writes_materialization_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "curriculum_coverage_preview.json",
        "digest_pointer.json",
        "private/authoritative_ledger_update_materialization_only.json",
        "private/authoritative_update_evidence_rows.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    assert hashlib.sha256((out / "private/authoritative_update_evidence_rows.jsonl").read_bytes()).hexdigest() == stage.EXPECTED_HASHES["stage12635_rows_bytes"]


def test_generated_artifacts_match_current_materialization():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_update_materialization_only.json")
    coverage = read_json(out / "curriculum_coverage_preview.json")
    assert summary == external
    assert summary["authoritative_ledger_updated"] is True
    assert summary["authoritative_admitted_train_support_tasks_after_update"] == 190
    assert summary["authoritative_gap_to_500_after_update"] == 310
    assert summary["training_allowed"] is False
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_authoritative_ledger_update_materialization_sha256"] == stable(private)
    assert pointer["authoritative_ledger_update_materialization_sha256"] == stable(private["authoritative_ledger_update_materialization"])
    assert pointer["curriculum_coverage_preview_sha256"] == stable(coverage)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_no_training_authority():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json", stage.OUT / "curriculum_coverage_preview.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("dataset_rows_admitted") is not True
        assert record.get("level_3_materialized") is not True
