from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12682_precise_link_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12682", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_gates_closed(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_exact_stage12681_artifacts() -> None:
    summary, audit, contract, rows = stage.load_inputs()
    assert summary["recommended_next_stage"] == stage.STAGE
    assert audit["next_required_action"] == stage.STAGE
    assert contract["rows_sha256"] == "7157befeeac5051b40efc406b3023ecdc2b47a493fd2dd6c156832b7d434f694"
    assert len(rows) == 72457


def test_review_detects_semantic_quality_blockers() -> None:
    *_, rows = stage.load_inputs()
    review = stage.review_rows(rows)
    assert review["symbol_keys_with_multiple_definition_files"] == 3546
    assert review["ambiguous_reference_rows"] == 5730
    assert review["identical_input_multiple_target_groups"] == 3071
    assert review["maximum_targets_for_identical_input"] == 25
    assert review["missing_definition_reference_rows"] == 7612
    assert review["evidence_target_leak_rows"] == 72457
    assert review["definition_reference_provenance_claim_rows"] == 45308
    assert review["cross_split_endpoint_groups"] == 59
    assert review["semantic_duplicate_excess_rows"] == 4053
    assert review["semantic_duplicate_signatures"] == 2042


def test_review_confirms_hygiene_and_closed_authority() -> None:
    *_, rows = stage.load_inputs()
    review = stage.review_rows(rows)
    for field in (
        "duplicate_row_ids", "schema_error_rows", "authority_open_rows", "raw_source_body_rows",
        "absolute_path_rows", "forbidden_marker_rows", "unsupported_link_type_rows", "evidence_mismatch_rows",
        "input_target_leak_rows", "file_identity_conflict_ids", "cross_split_repo_digest_groups",
    ):
        assert review[field] == 0


def test_build_packet_blocks_and_routes_to_semantic_repair() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "BLOCKED_PRECISE_LINK_LABEL_LEAKAGE_AMBIGUITY_AND_SPLIT_CONTAMINATION"
    assert summary["recommended_next_stage"] == "stage12683_precise_link_semantic_repair_preflight_only"
    assert summary["hygiene_review_passed"] is False
    assert summary["label_precision_review_passed"] is False
    assert summary["shortcut_review_passed"] is False
    assert summary["training_admission_review_passed"] is False
    assert summary["training_source_rows_admitted"] == 0
    assert audit["review"]["precise_link_rows_reviewed"] == 72457
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "schema_authority_and_hygiene",
        "unambiguous_symbol_definition_links",
        "duplicate_and_cross_split_shortcuts",
        "training_authority",
    ]
    assert_gates_closed(summary)
    assert_gates_closed(audit)


def test_build_writes_hash_consistent_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "precise_link_independent_review_audit.json",
        "private/precise_link_independent_review_checks.jsonl",
        "private/precise_link_independent_review_packet.json",
        "summary.json",
    ]
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/precise_link_independent_review_packet.json")
    audit = read_json(out / "precise_link_independent_review_audit.json")
    assert summary == read_json(summary_path)
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "precise_link_independent_review_audit.json")
    assert summary == external
    assert summary["precise_link_rows_reviewed"] == 72457
    assert audit["decision"] == summary["decision"]
    assert_gates_closed(summary)
    assert_gates_closed(audit)
