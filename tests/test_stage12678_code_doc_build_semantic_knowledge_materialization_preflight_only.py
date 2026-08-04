from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12678", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_rows(path: Path, limit: int | None = None):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            rows.append(json.loads(line))
            if limit is not None and len(rows) >= limit:
                break
    return rows


def assert_execution_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_stage12676_and_repo_index() -> None:
    summary76, repos = stage.load_inputs()
    assert summary76["adapter_candidate_rows"] == 28618
    assert len(repos) == 500


def test_generated_summary_and_audit_counts() -> None:
    summary = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "deep_repo_code_knowledge_materialization_audit.json")
    assert summary["decision"] == "DEEP_REPO_CODE_KNOWLEDGE_MATERIALIZED_REVIEW_REQUIRED"
    assert summary["materialized_rows"] == 120000
    assert summary["source_files_scanned"] == 42760
    assert summary["objective_family_count"] == 11
    assert summary["training_source_rows_admitted"] == 0
    assert audit["objective_counts"] == {
        "build_code_association_fact": 670,
        "deep_file_role_language_fact": 12526,
        "doc_code_association_fact": 60,
        "maintenance_vocabulary_fact": 11974,
        "nonpython_symbol_definition_fact": 33232,
        "nonpython_syntax_summary_fact": 7379,
        "python_import_api_fact": 12960,
        "python_symbol_definition_fact": 29882,
        "python_syntax_summary_fact": 2767,
        "test_file_association_fact": 1586,
        "test_framework_signal_fact": 6964,
    }
    assert audit["raw_source_body_rows"] == 0
    assert audit["absolute_path_rows"] == 0
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_deep_rows_have_required_source_derived_objectives_without_raw_body() -> None:
    rows_path = stage.OUT / "private/deep_repo_code_knowledge_rows.jsonl"
    rows = read_rows(rows_path, limit=5000)
    objectives = {row["objective_family"] for row in rows}
    assert "python_import_api_fact" in objectives or "nonpython_symbol_definition_fact" in objectives
    first = rows[0]
    assert first["training_stage"] == "repo_and_code_knowledge.deep_semantic"
    assert first["evidence"]["raw_source_body_included"] is False
    assert first["evidence"]["absolute_path_included"] is False
    assert "opaque_file_id" in first["input_state"] or first["objective_family"].endswith("association_fact")
    assert all(value is False for value in first["authority"].values())
    stage.assert_no_forbidden(first, "first_row")


def test_artifact_hash_pointers_match() -> None:
    summary = read_json(stage.OUT / "summary.json")
    contract = read_json(stage.OUT / "contract.json")
    private = read_json(stage.OUT / "private/deep_repo_code_knowledge_packet.json")
    audit = read_json(stage.OUT / "deep_repo_code_knowledge_materialization_audit.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert summary == read_json(stage.SUMMARY)


def test_public_artifacts_are_sanitized() -> None:
    for path in [
        stage.SUMMARY,
        stage.OUT / "summary.json",
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
        stage.OUT / "deep_repo_code_knowledge_materialization_audit.json",
    ]:
        stage.assert_no_forbidden(path.read_text(encoding="utf-8"), path.name)


def test_row_and_check_file_counts() -> None:
    rows_path = stage.OUT / "private/deep_repo_code_knowledge_rows.jsonl"
    checks_path = stage.OUT / "private/deep_repo_code_knowledge_checks.jsonl"
    assert sum(1 for _ in rows_path.open(encoding="utf-8")) == 120000
    assert sum(1 for _ in checks_path.open(encoding="utf-8")) == 6
