from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12681_precise_symbol_doc_test_link_materialization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12681", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


EXPECTED_OBJECTIVE_COUNTS = {
    "precise_build_symbol_reference_link": 2410,
    "precise_doc_symbol_reference_link": 5898,
    "precise_symbol_definition_file_link": 45308,
    "precise_test_symbol_reference_link": 18841,
}
EXPECTED_SPLIT_COUNTS = {"eval": 16110, "strict_eval": 15085, "train": 41262}


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_execution_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_stage12680_and_repo_inventory() -> None:
    summary80, audit80, repos = stage.load_inputs()
    assert summary80["next_required_action"] == stage.STAGE
    assert summary80["adapter_candidate_rows"] == 97462
    assert audit80["upstream_review_cross_split_source_file_digest_groups"] == 1
    assert len(repos) == 500


def test_materialize_rows_builds_precise_link_scale_and_distribution() -> None:
    _, _, repos = stage.load_inputs()
    rows, stats = stage.materialize_rows(repos)
    objective_counts = {}
    split_counts = {}
    for row in rows:
        objective_counts[row["objective_family"]] = objective_counts.get(row["objective_family"], 0) + 1
        split_counts[row["split"]] = split_counts.get(row["split"], 0) + 1
    assert len(rows) == 72457
    assert dict(sorted(objective_counts.items())) == EXPECTED_OBJECTIVE_COUNTS
    assert dict(sorted(split_counts.items())) == EXPECTED_SPLIT_COUNTS
    assert stats == {
        "linkable_reference_files": 6062,
        "max_link_rows_per_file": 40,
        "max_rows": 80000,
        "max_symbols_per_repo": 500,
        "repositories_seen": 500,
        "repositories_with_symbols": 326,
        "source_files_scanned": 42760,
    }
    first = rows[0]
    assert first["authority"] == {
        "body_emission_authorized": False,
        "loss_authorized": False,
        "model_execution_authorized": False,
        "optimizer_step_authorized": False,
        "runtime_authorized": False,
        "source_emission_authorized": False,
        "training_allowed": False,
        "training_run_allowed": False,
    }
    assert first["quality"]["precise_link_derived_from_literal_symbol_reference"] is True
    stage.assert_no_forbidden(first, "first_precise_link_row")


def test_build_packet_keeps_training_closed_and_routes_to_review() -> None:
    summary, audit, checks, rows = stage.build_packet()
    assert summary["decision"] == "PRECISE_SYMBOL_DOC_TEST_LINKS_MATERIALIZED_REVIEW_REQUIRED"
    assert summary["materialized_rows"] == 72457
    assert summary["split_counts"] == EXPECTED_SPLIT_COUNTS
    assert summary["recommended_next_stage"] == "stage12682_precise_link_independent_review_only"
    assert summary["training_source_rows_admitted"] == 0
    assert audit["objective_counts"] == EXPECTED_OBJECTIVE_COUNTS
    assert audit["raw_source_body_rows"] == 0
    assert audit["absolute_path_rows"] == 0
    assert audit["training_source_rows_admitted"] == 0
    assert len(rows) == 72457
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "independent_review",
        "training_authority",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, checks, _ = stage.build_packet()
    stage.assert_no_forbidden(summary, "summary")
    stage.assert_no_forbidden(audit, "audit")
    stage.assert_no_forbidden(checks, "checks")


def test_build_writes_precise_link_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "precise_symbol_doc_test_link_materialization_audit.json",
        "private/precise_symbol_doc_test_link_checks.jsonl",
        "private/precise_symbol_doc_test_link_packet.json",
        "private/precise_symbol_doc_test_link_rows.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/precise_symbol_doc_test_link_packet.json")
    audit = read_json(out / "precise_symbol_doc_test_link_materialization_audit.json")
    rows = [json.loads(line) for line in (out / "private/precise_symbol_doc_test_link_rows.jsonl").read_text().splitlines()]
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert pointer["rows_sha256"] == stable(rows)
    assert len(rows) == 72457


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "precise_symbol_doc_test_link_materialization_audit.json")
    assert summary == external
    assert summary["materialized_rows"] == 72457
    assert audit["objective_counts"] == EXPECTED_OBJECTIVE_COUNTS
    assert audit["source_scan_stats"]["source_files_scanned"] == 42760
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
