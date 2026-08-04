import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12632_authoritative_ledger_dry_run_authority_source_packet_design_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12632", SCRIPT)
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

def test_load_stage12631_requires_design_only_and_no_authority():
    loaded = stage.load_stage12631()
    summary = loaded["summary"]
    assert summary["dry_run_authority_source_packet_design_preflight_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["dry_run_authorization_granted"] is False
    assert summary["stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed"] is False
    assert stable(loaded["design"]) == stage.EXPECTED_HASHES["stage12631_authority_packet_design"]

def test_source_packet_is_present_but_non_authorizing():
    creation = stage.build_creation(stage.load_stage12631())
    packet = creation["authority_source_packet"]
    assert creation["creation_scope"] == "dry_run_authority_source_packet_creation_only"
    assert creation["dry_run_authority_source_packet_present"] is True
    assert creation["dry_run_authorization_granted"] is False
    assert creation["dry_run_performed"] is False
    assert packet["packet_scope"] == "candidate_ledger_dry_run_authority_source_packet_non_executable"
    assert packet["candidate_dry_run_authorization_granted_now"] is False
    assert packet["dry_run_execution_allowed_now"] is False
    assert packet["training_allowed_now"] is False

def test_packet_keeps_execution_update_admission_training_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12631())
    assert summary["decision"] == "DRY_RUN_AUTHORITY_SOURCE_PACKET_CREATED_NO_AUTHORIZATION_GRANTED"
    assert summary["dry_run_authority_source_packet_creation_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["dry_run_authorization_granted"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["stage12633_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["candidate_artifacts_written"] == 0
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False
    assert contract["private_source_packet_creation_sha256"] == stable(private)
    assert summary["source_packet_creation_sha256"] == stable(private["source_packet_creation"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)

def test_build_writes_only_source_packet_creation_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == ["contract.json", "digest_pointer.json", "private/authoritative_ledger_dry_run_authority_source_packet_creation_only.json", "summary.json"]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")

def test_generated_artifacts_match_current_source_packet_creation():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_creation_only.json")
    assert summary == external
    assert summary["dry_run_authority_source_packet_creation_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is True
    assert summary["dry_run_authorization_granted"] is False
    assert summary["training_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_creation"] == 158
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_source_packet_creation_sha256"] == stable(private)
    assert pointer["source_packet_creation_sha256"] == stable(private["source_packet_creation"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)

def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"dry_run_authority_source_packet_creation_only", "dry_run_authority_source_packet_present", "vm_branch_remains_paused"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
