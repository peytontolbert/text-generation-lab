import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12635_authoritative_ledger_update_dry_run_materialization_only.py"
SPEC = importlib.util.spec_from_file_location("stage12635", SCRIPT)
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


def test_load_authorization_requires_scoped_stage12634_gate():
    loaded = stage.load_authorization()
    summary = loaded["summary"]
    assert summary["dry_run_authorization_granted"] is True
    assert summary["dry_run_authorized"] is True
    assert summary["authoritative_ledger_dry_run_allowed"] is True
    assert summary["stage12635_authoritative_ledger_update_dry_run_only_allowed"] is True
    assert summary["candidate_ledger_materialized"] is False
    assert summary["authoritative_ledger_updated"] is False
    assert stable(loaded["authorization"]) == stage.EXPECTED_HASHES["stage12634_authorization"]


def test_candidate_source_is_pinned_and_guarded():
    source = stage.load_candidate_source()
    ledger = source["ledger"]
    assert len(source["rows"]) == 99
    assert hashlib.sha256(source["rows_bytes"]).hexdigest() == stage.EXPECTED_HASHES["stage12417_rows_bytes"]
    assert ledger["current_admitted_train_support_tasks"] == 190
    assert ledger["remaining_gap_to_500"] == 310
    assert ledger["guardrail_scan_passed"] is True
    assert ledger["training_allowed"] is False
    assert ledger["raw_leak_count"] == 0
    assert ledger["overclaim_count"] == 0


def test_materialization_writes_candidate_only_and_keeps_admission_closed():
    materialization, public_diff, private_manifest = stage.build_materialization(stage.load_authorization(), stage.load_candidate_source())
    assert materialization["materialization_scope"] == "candidate_ledger_dry_run_materialization_only"
    assert materialization["authoritative_ledger_dry_run_performed"] is True
    assert materialization["candidate_ledger_materialized"] is True
    assert materialization["candidate_rows_materialized"] is True
    assert materialization["dry_run_candidate_artifacts_written"] is True
    assert materialization["authoritative_ledger_update_performed"] is False
    assert materialization["new_admission_performed"] is False
    assert materialization["training_allowed_after_dry_run"] is False
    assert public_diff["candidate_count_after_dry_run"] == 190
    assert private_manifest["candidate_projection_row_count"] == 99
    assert private_manifest["candidate_total_count_after_dry_run"] == 190
    requirements = private_manifest["materialized_private_manifest_requirements"]
    assert set(requirements) == {"merged_row_manifest", "supersession_manifest", "direct_log_merge_manifest", "duplicate_policy_manifest", "guardrail_manifest"}
    assert requirements["merged_row_manifest"]["projection_rows"] == 99
    assert requirements["merged_row_manifest"]["event_local_base_rows_referenced"] == 91
    assert requirements["supersession_manifest"]["net_delta"] == 14
    assert requirements["direct_log_merge_manifest"]["direct_log_projection_rows"] == 18
    assert requirements["duplicate_policy_manifest"]["post_update_duplicate_extra_rows_required"] == 0
    assert requirements["guardrail_manifest"]["scan_passed"] is True


def test_public_private_contract_keeps_non_dry_run_gates_false():
    summary, contract, private, public_diff, private_manifest = stage.build_packet(stage.load_authorization(), stage.load_candidate_source())
    assert summary["decision"] == "CANDIDATE_LEDGER_DRY_RUN_MATERIALIZED_NO_AUTHORITATIVE_UPDATE_OR_ADMISSION"
    for field in ("dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "dry_run_candidate_artifacts_written", "vm_branch_remains_paused"):
        assert summary[field] is True
        assert contract[field] is True
        assert private[field] is True
    assert summary["authoritative_ledger_updated"] is False
    assert summary["training_allowed"] is False
    assert summary["dataset_rows_admitted"] is False
    assert summary["candidate_train_support_tasks_after_dry_run"] == 190
    assert summary["authoritative_admitted_train_support_tasks_after_dry_run"] == 158
    assert summary["materialized_projection_rows"] == 99
    assert summary["event_local_base_rows_referenced"] == 91
    assert contract["private_candidate_manifest_sha256"] == stable(private_manifest)
    assert summary["public_summary_diff_sha256"] == stable(public_diff)
    for record in (summary, contract, private, public_diff):
        assert_false_boundaries(record)


def test_build_writes_only_dry_run_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "candidate_summary_diff.json",
        "contract.json",
        "digest_pointer.json",
        "private/authoritative_ledger_update_dry_run_materialization_only.json",
        "private/candidate_ledger_dry_run_manifest.json",
        "private/candidate_train_support_rows_dry_run.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_materialization():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/authoritative_ledger_update_dry_run_materialization_only.json")
    public_diff = read_json(out / "candidate_summary_diff.json")
    private_manifest = read_json(out / "private/candidate_ledger_dry_run_manifest.json")
    rows_bytes = (out / "private/candidate_train_support_rows_dry_run.jsonl").read_bytes()
    assert summary == external
    assert hashlib.sha256(rows_bytes).hexdigest() == stage.EXPECTED_HASHES["stage12417_rows_bytes"]
    assert summary["candidate_train_support_tasks_after_dry_run"] == 190
    assert summary["authoritative_admitted_train_support_tasks_after_dry_run"] == 158
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_dry_run_materialization_sha256"] == stable(private)
    assert pointer["dry_run_materialization_sha256"] == stable(private["dry_run_materialization"])
    assert summary["public_summary_diff_sha256"] == stable(public_diff)
    assert summary["private_candidate_manifest_sha256"] == stable(private_manifest)
    for record in (summary, contract, pointer, private, public_diff):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_and_only_scoped_true_gates():
    allowed_true = {"dry_run_authorization_granted", "dry_run_authorized", "authoritative_ledger_dry_run_allowed", "stage12635_authoritative_ledger_update_dry_run_only_allowed", "authoritative_ledger_dry_run_performed", "authoritative_ledger_update_dry_run_materialized", "candidate_ledger_materialized", "candidate_rows_materialized", "dry_run_candidate_artifacts_written", "candidate_projection_rows_materialized", "vm_branch_remains_paused"}
    public_paths = [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json", stage.OUT / "candidate_summary_diff.json"]
    for path in public_paths:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        if path.name != "candidate_summary_diff.json":
            assert {key for key, value in record.items() if value is True} == allowed_true
