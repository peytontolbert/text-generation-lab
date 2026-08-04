from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12678_deep_repo_code_knowledge_materialization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12678", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_execution_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_deep_knowledge_sources() -> None:
    stage12676, repos, symbols, retrieval_docs, selected, verifier = stage.load_inputs()
    assert stage12676["adapter_candidate_rows"] == 28618
    assert len(repos) == 500
    assert len(symbols) == 1068
    assert len(retrieval_docs) == 80
    assert len(selected) == 55
    assert len(verifier) == 54


def test_materialize_rows_covers_deep_knowledge_lanes_without_bodies() -> None:
    _, repos, symbols, retrieval_docs, selected, verifier = stage.load_inputs()
    rows = stage.materialize_rows(repos, symbols, retrieval_docs, selected, verifier)
    assert len(rows) == 15286
    objectives = {row["objective_family"] for row in rows}
    assert "syntax_api_structural_profile" in objectives
    assert "doc_code_test_relationship" in objectives
    assert "symbol_reference_prediction_structural" in objectives
    assert "test_file_association_bucket" in objectives
    assert "verifier_evidence_role_choice_summary" in objectives
    first = rows[0]
    assert first["row_id"].startswith("stage12678_deep_repo_code_knowledge_")
    assert first["evidence"]["raw_source_included"] is False
    assert first["evidence"]["absolute_path_included"] is False
    assert first["evidence"]["source_body_included"] is False
    stage.assert_no_forbidden(first, "first_row")


def test_summarize_reports_expected_counts_and_keeps_training_closed() -> None:
    stage12676, repos, symbols, retrieval_docs, selected, verifier = stage.load_inputs()
    rows = stage.materialize_rows(repos, symbols, retrieval_docs, selected, verifier)
    summary, audit, checks = stage.summarize(rows, stage12676)
    assert summary["decision"] == "DEEP_REPO_CODE_KNOWLEDGE_ROWS_MATERIALIZED_REVIEW_REQUIRED"
    assert summary["materialized_deep_knowledge_rows"] == 15286
    assert summary["objective_counts"] == {
        "doc_code_test_relationship": 1774,
        "issue_maintenance_vocabulary_proxy": 3937,
        "old_language_retention_flag": 500,
        "retrieval_doc_role_proxy": 80,
        "retrieval_file_association_proxy": 80,
        "retrieval_query_surface_proxy": 80,
        "selected_test_evidence_shape_summary": 55,
        "selected_test_loss_contract_summary": 55,
        "selected_test_task_family_summary": 55,
        "symbol_graph_feature_prediction": 3204,
        "symbol_reference_prediction_structural": 1068,
        "syntax_api_structural_profile": 2236,
        "test_file_association_bucket": 2000,
        "verifier_evidence_language_summary": 54,
        "verifier_evidence_role_choice_summary": 54,
        "verifier_option_set_summary": 54,
    }
    assert audit["duplicate_row_hashes"] == 0
    assert audit["authority_open_rows"] == 0
    assert audit["template_marker_or_forbidden_hits"] == 0
    assert audit["raw_source_body_rows"] == 0
    assert audit["absolute_path_rows"] == 0
    assert audit["training_source_rows_admitted"] == 0
    assert audit["coverage"]["direct_source_body_syntax_api_mining"] == "blocked_pending_controlled_parser_no_body_emission"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "direct_source_body_syntax_api_parser",
        "independent_training_admission",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    stage12676, repos, symbols, retrieval_docs, selected, verifier = stage.load_inputs()
    rows = stage.materialize_rows(repos, symbols, retrieval_docs, selected, verifier)
    summary, audit, checks = stage.summarize(rows, stage12676)
    stage.assert_no_forbidden(summary, "summary")
    stage.assert_no_forbidden(audit, "audit")
    stage.assert_no_forbidden(checks, "checks")


def test_build_writes_stage_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "deep_repo_code_knowledge_examples.jsonl",
        "deep_repo_code_knowledge_materialization_audit.json",
        "digest_pointer.json",
        "private/deep_repo_code_knowledge_materialization_checks.jsonl",
        "private/deep_repo_code_knowledge_materialization_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/deep_repo_code_knowledge_materialization_packet.json")
    audit = read_json(out / "deep_repo_code_knowledge_materialization_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "deep_repo_code_knowledge_examples.jsonl").open()) == 15286
    assert sum(1 for _ in (out / "private/deep_repo_code_knowledge_materialization_checks.jsonl").open()) == 8


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "deep_repo_code_knowledge_materialization_audit.json")
    assert summary == external
    assert summary["materialized_deep_knowledge_rows"] == 15286
    assert summary["training_source_rows_admitted"] == 0
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
