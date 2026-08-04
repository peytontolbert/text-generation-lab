import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12636_candidate_ledger_dry_run_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12636", SCRIPT)
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


def test_load_stage12635_pins_dry_run_artifacts_and_projection_rows():
    loaded = stage.load_stage12635()
    assert loaded["summary"] == read_json(stage.S12635_SUMMARY)
    assert stable(loaded["summary"]) == stage.EXPECTED_HASHES["stage12635_summary"]
    assert stable(loaded["materialization"]) == stage.EXPECTED_HASHES["stage12635_materialization"]
    assert stable(loaded["private_manifest"]) == stage.EXPECTED_HASHES["stage12635_private_manifest"]
    assert len(loaded["projection_rows"]) == 99
    assert loaded["summary"]["candidate_train_support_tasks_after_dry_run"] == 190
    assert loaded["summary"]["authoritative_admitted_train_support_tasks_after_dry_run"] == 158


def test_validate_stage12635_requires_counts_manifests_and_closed_gates():
    loaded = stage.load_stage12635()
    stage.validate_stage12635(loaded)
    requirements = loaded["private_manifest"]["materialized_private_manifest_requirements"]
    assert set(requirements) == {"merged_row_manifest", "supersession_manifest", "direct_log_merge_manifest", "duplicate_policy_manifest", "guardrail_manifest"}
    assert requirements["merged_row_manifest"]["projection_rows"] == 99
    assert requirements["merged_row_manifest"]["event_local_base_rows_referenced"] == 91
    assert requirements["supersession_manifest"]["net_delta"] == 14
    assert requirements["direct_log_merge_manifest"]["direct_log_projection_rows"] == 18
    assert requirements["duplicate_policy_manifest"]["post_update_duplicate_extra_rows_required"] == 0


def test_review_passes_but_does_not_authorize_update_or_admission():
    review = stage.build_review(stage.load_stage12635())
    assert review["review_scope"] == "candidate_ledger_dry_run_independent_review_only"
    assert review["review_status"] == "candidate_ledger_dry_run_review_passed_no_authoritative_update_or_admission"
    assert review["candidate_count_after_review"] == 190
    assert review["authoritative_count_after_review"] == 158
    assert review["materialized_projection_rows"] == 99
    assert review["event_local_base_rows_referenced"] == 91
    assert review["authoritative_ledger_update_performed"] is False
    assert review["new_admission_performed"] is False
    assert review["training_allowed_after_review"] is False


def test_public_private_contract_keeps_non_review_gates_false():
    summary, contract, private = stage.build_packet(stage.load_stage12635())
    assert summary["decision"] == "CANDIDATE_LEDGER_DRY_RUN_INDEPENDENT_REVIEW_PASSED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION"
    allowed_true = {"candidate_dry_run_independent_review_only", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "candidate_projection_rows_materialized", "dry_run_candidate_artifacts_written", "vm_branch_remains_paused"}
    for record in (summary, contract, private):
        assert {key for key, value in record.items() if value is True} == allowed_true
        assert_false_boundaries(record)
    assert summary["authoritative_ledger_update_allowed"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False
    assert contract["private_candidate_dry_run_independent_review_sha256"] == stable(private)


def test_build_writes_only_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == ["contract.json", "digest_pointer.json", "private/candidate_ledger_dry_run_independent_review_only.json", "summary.json"]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_review():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/candidate_ledger_dry_run_independent_review_only.json")
    assert summary == external
    assert summary["candidate_train_support_tasks_after_review"] == 190
    assert summary["authoritative_admitted_train_support_tasks_after_review"] == 158
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_candidate_dry_run_independent_review_sha256"] == stable(private)
    assert pointer["candidate_dry_run_independent_review_sha256"] == stable(private["candidate_dry_run_independent_review"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"candidate_dry_run_independent_review_only", "dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "candidate_projection_rows_materialized", "dry_run_candidate_artifacts_written", "vm_branch_remains_paused"}
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert {key for key, value in record.items() if value is True} == allowed_true
