import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12633_authoritative_ledger_dry_run_authority_source_packet_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12633", SCRIPT)
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


def test_load_stage12632_requires_source_packet_but_no_authorization():
    loaded = stage.load_stage12632()
    summary = loaded["summary"]
    packet = loaded["packet"]
    assert summary["dry_run_authority_source_packet_creation_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is True
    assert summary["dry_run_authorization_granted"] is False
    assert summary["stage12633_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert packet["packet_scope"] == "candidate_ledger_dry_run_authority_source_packet_non_executable"
    assert stable(packet) == stage.EXPECTED_HASHES["stage12632_authority_source_packet"]


def test_independent_review_passes_packet_shape_but_does_not_authorize():
    review = stage.build_review(stage.load_stage12632())
    assert review["review_scope"] == "dry_run_authority_source_packet_independent_review_only"
    assert review["review_status"] == "independent_review_passed_packet_remains_non_authorizing"
    assert review["dry_run_authorization_status"] == "not_granted_after_independent_source_packet_review"
    assert review["dry_run_authority_source_packet_independent_review_only"] is True
    assert review["dry_run_authority_source_packet_present"] is True
    assert review["dry_run_authorization_granted"] is False
    assert review["dry_run_performed"] is False
    assert review["training_allowed_after_review"] is False
    assert review["candidate_artifacts_written"] == 0


def test_review_keeps_execution_update_admission_training_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12632())
    assert summary["decision"] == "DRY_RUN_AUTHORITY_SOURCE_PACKET_INDEPENDENT_REVIEW_PASSED_NO_DRY_RUN_AUTHORIZATION"
    assert summary["dry_run_authority_source_packet_independent_review_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["dry_run_authorization_granted"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["stage12634_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["candidate_artifacts_written"] == 0
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False
    assert contract["private_source_packet_independent_review_sha256"] == stable(private)
    assert summary["source_packet_independent_review_sha256"] == stable(private["source_packet_independent_review"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_source_packet_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == ["contract.json", "digest_pointer.json", "private/authoritative_ledger_dry_run_authority_source_packet_independent_review_only.json", "summary.json"]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_source_packet_review():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_independent_review_only.json")
    assert summary == external
    assert summary["dry_run_authority_source_packet_independent_review_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is True
    assert summary["dry_run_authorization_granted"] is False
    assert summary["training_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_source_packet_independent_review_sha256"] == stable(private)
    assert pointer["source_packet_independent_review_sha256"] == stable(private["source_packet_independent_review"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"dry_run_authority_source_packet_independent_review_only", "dry_run_authority_source_packet_present", "vm_branch_remains_paused"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
