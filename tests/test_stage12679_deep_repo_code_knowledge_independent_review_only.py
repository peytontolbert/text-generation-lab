from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12679_deep_repo_code_knowledge_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12679", SCRIPT)
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


def test_load_inputs_pins_stage12678_deep_materialization() -> None:
    summary78, audit78, contract78, rows = stage.load_inputs()
    assert summary78["stage"] == "stage12678_code_doc_build_semantic_knowledge_materialization_preflight_only"
    assert summary78["materialized_rows"] == 120000
    assert audit78["source_scan_stats"]["source_files_scanned"] == 42760
    assert contract78["rows_sha256"] == "9ae16f03a35a77243f7d45348f90b2b7102161487111e4d54e1c37eeaff9f8f5"
    assert len(rows) == 120000


def test_review_rows_finds_exact_blockers_without_hygiene_failures() -> None:
    _, _, _, rows = stage.load_inputs()
    review = stage.review_rows(rows)
    assert review["deep_knowledge_rows_reviewed"] == 120000
    assert review["objective_counts"] == stage.EXPECTED_OBJECTIVE_COUNTS
    assert review["split_counts"] == stage.EXPECTED_SPLIT_COUNTS
    assert review["duplicate_row_ids"] == 0
    assert review["semantic_duplicate_rows_excluding_row_id"] == 4631
    assert review["semantic_duplicate_signatures_excluding_row_id"] == 2553
    assert review["target_duplicate_instances"] == 80334
    assert review["target_duplicate_signatures"] == 5367
    assert review["target_signatures_cross_split"] == 1068
    assert review["cross_split_repo_digest_groups"] == 0
    assert review["cross_split_source_file_digest_groups"] == 1
    assert review["authority_open_rows"] == 0
    assert review["raw_source_body_rows"] == 0
    assert review["absolute_path_rows"] == 0
    assert review["forbidden_marker_rows"] == 0
    assert review["missing_objective_split_pairs"] == 0


def test_build_packet_blocks_training_and_routes_to_stage12680() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "BLOCKED_DEEP_KNOWLEDGE_TRAINING_ADMISSION_REQUIRES_FILE_SPLIT_AND_SHORTCUT_ADAPTER_REPAIR"
    assert summary["materialization_review_passed"] is True
    assert summary["training_admission_review_passed"] is False
    assert summary["deep_knowledge_rows_reviewed"] == 120000
    assert summary["training_source_rows_admitted"] == 0
    assert summary["file_split_repair_required"] is True
    assert summary["shortcut_adapter_required"] is True
    assert summary["semantic_duplicate_repair_required"] is True
    assert summary["trainer_adapter_required"] is True
    assert summary["recommended_next_stage"] == "stage12680_deep_repo_code_knowledge_adapter_and_shortcut_preflight_only"
    assert audit["trainer_adapter_fit"] == "blocked_pending_deep_repo_code_knowledge_adapter_binding"
    assert audit["shortcut_baseline_status"] == "blocked_pending_duplicate_target_quarantine_or_weighting"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "file_digest_split_isolation",
        "semantic_duplicate_rows",
        "target_duplicate_shortcut_risk",
        "trainer_adapter_binding",
        "training_authority",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, checks = stage.build_packet()
    stage.assert_no_forbidden(summary, "summary")
    stage.assert_no_forbidden(audit, "audit")
    stage.assert_no_forbidden(checks, "checks")


def test_build_writes_review_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "deep_repo_code_knowledge_independent_review_audit.json",
        "digest_pointer.json",
        "private/deep_repo_code_knowledge_independent_review_checks.jsonl",
        "private/deep_repo_code_knowledge_independent_review_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/deep_repo_code_knowledge_independent_review_packet.json")
    audit = read_json(out / "deep_repo_code_knowledge_independent_review_audit.json")
    checks_path = out / "private/deep_repo_code_knowledge_independent_review_checks.jsonl"
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert pointer["checks_sha256"] == hashlib.sha256(checks_path.read_bytes()).hexdigest()
    assert sum(1 for _ in checks_path.open(encoding="utf-8")) == 9


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "deep_repo_code_knowledge_independent_review_audit.json")
    assert summary == external
    assert summary["deep_knowledge_rows_reviewed"] == 120000
    assert summary["cross_split_source_file_digest_groups"] == 1
    assert summary["semantic_duplicate_rows_excluding_row_id"] == 4631
    assert summary["target_duplicate_instances"] == 80334
    assert summary["training_admission_review_passed"] is False
    assert summary["training_source_rows_admitted"] == 0
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
