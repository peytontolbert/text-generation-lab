import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12634_authoritative_ledger_dry_run_authorization_only.py"
SPEC = importlib.util.spec_from_file_location("stage12634", SCRIPT)
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


def test_predecessors_pin_review_and_non_authorized_state():
    loaded = stage.load_predecessors()
    assert loaded["stage12627_summary"]["dry_run_authorized"] is False
    assert loaded["stage12633_summary"]["dry_run_authorization_granted"] is False
    assert loaded["stage12633_summary"]["next_required_action"] == "separate_dry_run_authorization_decision_before_any_candidate_ledger_dry_run"
    assert stable(loaded["preflight"]) == stage.EXPECTED_HASHES["stage12627_preflight_review"]
    assert stable(loaded["source_packet_review"]) == stage.EXPECTED_HASHES["stage12633_source_packet_review"]


def test_authorization_is_dry_run_only():
    authorization = stage.build_authorization(stage.load_predecessors())
    assert authorization["authorization_scope"] == "candidate_ledger_dry_run_only"
    assert authorization["dry_run_authorization_granted"] is True
    assert authorization["dry_run_authorized"] is True
    assert authorization["authoritative_ledger_dry_run_allowed"] is True
    assert authorization["stage12635_authoritative_ledger_update_dry_run_only_allowed"] is True
    assert authorization["dry_run_performed"] is False
    assert authorization["authoritative_ledger_update_performed"] is False
    assert authorization["new_admission_performed"] is False
    assert authorization["training_allowed_after_authorization"] is False
    assert authorization["authorized_candidate_count"] == 190
    assert authorization["authoritative_count_at_authorization"] == 158


def test_public_private_contract_keeps_non_dry_run_gates_false():
    summary, contract, private = stage.build_packet(stage.load_predecessors())
    assert summary["decision"] == "CANDIDATE_LEDGER_DRY_RUN_AUTHORIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION"
    for field in ("dry_run_authorization_decision_only", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "vm_branch_remains_paused"):
        assert summary[field] is True
        assert contract[field] is True
        assert private[field] is True
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False
    assert summary["candidate_ledger_materialized"] is False
    assert contract["private_dry_run_authorization_sha256"] == stable(private)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_authorization_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == ["contract.json", "digest_pointer.json", "private/authoritative_ledger_dry_run_authorization_only.json", "summary.json"]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_authorization():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_dry_run_authorization_only.json")
    assert summary == external
    assert summary["dry_run_authorized"] is True
    assert summary["authoritative_admitted_train_support_tasks_after_authorization"] == 158
    assert summary["authorized_candidate_count"] == 190
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_dry_run_authorization_sha256"] == stable(private)
    assert pointer["dry_run_authorization_sha256"] == stable(private["dry_run_authorization"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"dry_run_authorization_decision_only", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "vm_branch_remains_paused"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
