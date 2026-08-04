from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12665_combined_curriculum_pack_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12665", SCRIPT)
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


def test_load_inputs_pins_stage12664_pack() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["combined"]) == 2445
    assert len(loaded["quarantined"]) == 22


def test_review_combined_pack_counts_and_quarantines() -> None:
    loaded = stage.load_inputs()
    audit = stage.review_combined(loaded["combined"], loaded["quarantined"])
    assert audit["review_decision"] == "PASS_COMBINED_CURRICULUM_PACK_COMPOSITION_NO_TRAINING_RUN"
    assert audit["combined_trainer_rows_reviewed"] == 2445
    assert audit["repo_code_rows_reviewed"] == 258
    assert audit["structured_repo_state_rows_reviewed"] == 2187
    assert audit["repo_code_quarantined_rows_preserved"] == 22
    assert audit["split_counts"] == stage.EXPECTED_SPLITS
    assert audit["objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["structured_state_duplicate_downweighted_rows"] == 1686
    assert audit["repo_code_symbol_quarantine_preserved"] is True
    assert_execution_gates_closed(audit)


def test_combined_manifest_has_no_forbidden_leaks() -> None:
    loaded = stage.load_inputs()
    encoded = json.dumps({"combined": loaded["combined"], "quarantined": loaded["quarantined"]}, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded


def test_build_packet_keeps_training_execution_blocked() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["combined_curriculum_pack_independently_reviewed"] is True
    assert summary["combined_curriculum_pack_review_passed"] is True
    assert summary["dataset_rows_admitted"] is True
    assert summary["combined_trainer_rows_reviewed"] == 2445
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["training_admitted"] is False
    assert summary["next_required_action"] == "stage12666_combined_curriculum_training_authorization_preflight_only"
    assert audit["next_required_action"] == summary["next_required_action"]
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == ["training_execution_authority"]
    assert_execution_gates_closed(summary)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)
        encoded = json.dumps(record, sort_keys=True)
        for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
            assert needle not in encoded


def test_build_writes_review_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/combined_curriculum_pack_review_packet.json",
        "private/review_checks.jsonl",
        "review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/combined_curriculum_pack_review_packet.json")
    audit = read_json(out / "review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["review_audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/review_checks.jsonl").open()) == 6


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "review_audit.json")
    assert summary == external
    assert summary["combined_trainer_rows_reviewed"] == 2445
    assert summary["training_allowed"] is False
    assert audit["review_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
