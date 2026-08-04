import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12637_authoritative_ledger_update_authorization_only.py"
SPEC = importlib.util.spec_from_file_location("stage12637", SCRIPT)
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


def test_load_stage12636_requires_review_passed_and_no_update():
    loaded = stage.load_stage12636()
    summary = loaded["summary"]
    assert summary["review_status"] == "candidate_ledger_dry_run_review_passed_no_authoritative_update_or_admission"
    assert summary["next_required_action"] == "separate_authoritative_ledger_update_authorization_decision"
    assert summary["candidate_train_support_tasks_after_review"] == 190
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert summary["authoritative_ledger_update_allowed"] is False
    assert stable(loaded["review"]) == stage.EXPECTED_HASHES["stage12636_review"]


def test_authorization_scope_allows_update_only_not_execution_of_update():
    authorization = stage.build_authorization(stage.load_stage12636())
    assert authorization["authorization_scope"] == "authoritative_ledger_update_only"
    assert authorization["authorized_next_stage"] == "stage12638_authoritative_ledger_update_materialization_only"
    assert authorization["authoritative_ledger_update_allowed"] is True
    assert authorization["stage12638_authoritative_ledger_update_materialization_only_allowed"] is True
    assert authorization["authoritative_ledger_update_performed"] is False
    assert authorization["authoritative_ledger_updated"] is False
    assert authorization["new_admission_performed"] is False
    assert authorization["training_allowed_after_authorization"] is False
    assert authorization["authorized_authoritative_count_after_update"] == 190


def test_public_private_contract_keeps_materialization_and_training_false():
    summary, contract, private = stage.build_packet(stage.load_stage12636())
    assert summary["decision"] == "AUTHORITATIVE_LEDGER_UPDATE_AUTHORIZED_NO_UPDATE_OR_ADMISSION_PERFORMED"
    allowed_true = {"authoritative_ledger_update_authorization_only", "authoritative_ledger_update_allowed", "stage12638_authoritative_ledger_update_materialization_only_allowed", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "candidate_projection_rows_materialized", "dry_run_candidate_artifacts_written", "vm_branch_remains_paused"}
    for record in (summary, contract, private):
        assert {key for key, value in record.items() if value is True} == allowed_true
        assert_false_boundaries(record)
    assert summary["authoritative_ledger_updated"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["training_allowed"] is False
    assert contract["private_authoritative_ledger_update_authorization_sha256"] == stable(private)


def test_build_writes_only_authorization_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == ["contract.json", "digest_pointer.json", "private/authoritative_ledger_update_authorization_only.json", "summary.json"]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_authorization():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_update_authorization_only.json")
    assert summary == external
    assert summary["authoritative_ledger_update_allowed"] is True
    assert summary["authoritative_ledger_updated"] is False
    assert summary["authorized_authoritative_train_support_tasks_after_update"] == 190
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_authoritative_ledger_update_authorization_sha256"] == stable(private)
    assert pointer["authoritative_ledger_update_authorization_sha256"] == stable(private["authoritative_ledger_update_authorization"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"authoritative_ledger_update_authorization_only", "authoritative_ledger_update_allowed", "stage12638_authoritative_ledger_update_materialization_only_allowed", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "candidate_projection_rows_materialized", "dry_run_candidate_artifacts_written", "vm_branch_remains_paused"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
