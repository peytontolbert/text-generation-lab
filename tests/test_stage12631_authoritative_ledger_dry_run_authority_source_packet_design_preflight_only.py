import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12631_authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12631", SCRIPT)
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


def test_load_stage12630_requires_request_review_only_and_no_authority():
    loaded = stage.load_stage12630()
    summary = loaded["summary"]
    assert summary["dry_run_authority_source_packet_request_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["dry_run_authorization_granted"] is False
    assert summary["dry_run_authorized"] is False
    assert summary["stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed"] is False
    assert summary["stage12631_allowed"] is False
    assert independent_stable_hash(loaded["request_review"]) == stage.EXPECTED_HASHES["stage12630_request_review"]


def test_design_is_future_shape_only_and_non_authorizing():
    design = stage.authority_packet_design()
    assert design["design_scope"] == "future_authority_source_packet_shape_only"
    assert "independent_review_before_any_dry_run_clause" in design["future_packet_must_include"]
    assert "authoritative_ledger_update" in design["future_packet_must_not_grant"]
    assert "dataset_admission" in design["future_packet_must_not_grant"]
    assert "training_or_eval_admission" in design["future_packet_must_not_grant"]
    assert "no_authority_source_packet" in design["stage12631_outputs"]
    assert "no_candidate_files" in design["stage12631_outputs"]


def test_design_preflight_records_no_authority_or_execution():
    preflight = stage.build_design_preflight(stage.load_stage12630())
    assert preflight["preflight_scope"] == "dry_run_authority_source_packet_design_preflight_only"
    assert preflight["preflight_status"] == "design_recorded_authority_source_packet_still_absent"
    assert preflight["dry_run_authorization_status"] == "not_granted_design_preflight_only"
    assert preflight["dry_run_authority_source_packet_present"] is False
    assert preflight["dry_run_authorization_granted"] is False
    assert preflight["dry_run_performed"] is False
    assert preflight["authoritative_count_after_preflight"] == 158
    assert preflight["authoritative_gap_after_preflight"] == 342
    assert preflight["conditional_candidate_count_if_later_authority_and_dry_run_pass"] == 190


def test_packet_keeps_authority_dry_run_update_admission_training_and_successor_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12630())
    assert summary["decision"] == "DRY_RUN_AUTHORITY_SOURCE_PACKET_DESIGN_PREFLIGHT_RECORDED_NO_AUTHORITY_GRANTED"
    assert summary["dry_run_authority_source_packet_design_preflight_only"] is True
    assert summary["vm_branch_remains_paused"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["dry_run_authorization_granted"] is False
    assert summary["stage12631_authoritative_ledger_dry_run_authority_source_packet_allowed"] is False
    assert summary["stage12632_authoritative_ledger_dry_run_authority_source_packet_allowed"] is False
    assert summary["stage12632_authoritative_ledger_update_dry_run_only_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["candidate_artifacts_written"] == 0
    assert summary["training_allowed"] is False
    assert contract["private_design_preflight_sha256"] == independent_stable_hash(private)
    assert summary["design_preflight_sha256"] == independent_stable_hash(private["design_preflight"])
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_only_design_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_design_preflight():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_dry_run_authority_source_packet_design_preflight_only.json")
    assert summary == external
    assert summary["dry_run_authority_source_packet_design_preflight_only"] is True
    assert summary["dry_run_authority_source_packet_present"] is False
    assert summary["stage12632_allowed"] is False
    assert summary["training_allowed"] is False
    assert summary["authoritative_admitted_train_support_tasks_after_preflight"] == 158
    assert summary["authoritative_gap_to_500_after_preflight"] == 342
    assert pointer["contract_sha256"] == independent_stable_hash(contract)
    assert pointer["private_design_preflight_sha256"] == independent_stable_hash(private)
    assert pointer["design_preflight_sha256"] == independent_stable_hash(private["design_preflight"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {
        "dry_run_authority_source_packet_design_preflight_only",
        "vm_branch_remains_paused",
    }
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
