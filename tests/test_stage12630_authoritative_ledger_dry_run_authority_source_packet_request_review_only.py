import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12630_authoritative_ledger_dry_run_authority_source_packet_request_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12630", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def independent_stable_hash(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


def test_load_stage12629_requires_request_only_and_no_authority():
    loaded = stage.load_stage12629()
    summary = loaded["summary"]
    assert summary["dry_run_authority_source_packet_request_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["dry_run_authorization_granted"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["stage12630_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12630_allowed"] is False
    assert independent_stable_hash(loaded["request_scope"]) == stage.EXPECTED_HASHES["stage12629_request_scope"]


def test_request_review_is_coherent_but_non_authorizing():
    review = stage.build_request_review(stage.load_stage12629())
    assert review["review_scope"] == "dry_run_authority_source_packet_request_only"
    assert review["review_status"] == "request_coherent_but_authority_source_packet_still_absent"
    assert review["dry_run_authorization_status"] == "not_granted_request_review_only"
    assert review["dry_run_authority_source_packet_present"] is False
    assert review["dry_run_authorization_granted"] is False
    assert review["dry_run_performed"] is False
    assert review["authoritative_count_after_review"] == 158
    assert review["authoritative_gap_after_review"] == 342
    assert review["conditional_candidate_count_if_later_authority_and_dry_run_pass"] == 190


def test_review_checks_preserve_request_only_boundary():
    review = stage.build_request_review(stage.load_stage12629())
    assert review["review_check_count"] == 6
    checks = {check["check_id"]: check for check in review["review_checks"]}
    assert checks["request_marker_present"]["request_only"] is True
    assert checks["authority_source_packet_absent"]["dry_run_authority_source_packet_present"] is False
    assert checks["dry_run_authorization_absent"]["dry_run_authorization_granted"] is False
    assert checks["future_authority_requires_independent_review"]["independent_review_required"] is True
    assert checks["training_admission_remains_separate"]["training_allowed"] is False


def test_packet_keeps_all_authority_dry_run_update_admission_training_and_successor_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12629())
    assert summary["decision"] == "DRY_RUN_AUTHORITY_SOURCE_PACKET_REQUEST_REVIEW_RECORDED_AUTHORITY_STILL_NOT_GRANTED"
    assert summary["dry_run_authority_source_packet_request_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["dry_run_authorization_granted"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["stage12630_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed"] is False
    assert summary["stage12631_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["candidate_artifacts_written"] == 0
    assert summary["training_allowed"] is False
    assert contract["private_request_review_sha256"] == independent_stable_hash(private)
    assert summary["request_review_sha256"] == independent_stable_hash(private["request_review"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_request_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_dry_run_authority_source_packet_request_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_request_review():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_request_only.json")
    assert summary == external
    assert summary["dry_run_authority_source_packet_request_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["stage12631_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert summary["authoritative_gap_to_500_after_review"] == 342
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_request_review_sha256"] == independent_stable_hash(private)
    assert pointer["request_review_sha256"] == independent_stable_hash(private["request_review"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {
        "dry_run_authority_source_packet_request_only",
        "vm_branch_remains_paused",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
