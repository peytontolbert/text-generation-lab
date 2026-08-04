from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12659_structured_repo_state_manifest_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12659", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert record[field] is False


def test_load_inputs_pins_stage12658_artifacts_and_gates() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["manifest"]) == 3975
    assert len(loaded["excluded"]) == 3


def test_review_manifest_accepts_as_review_input_not_admission() -> None:
    loaded = stage.load_inputs()
    audit, rows = stage.review_manifest(loaded["manifest"], loaded["excluded"])
    assert audit["review_decision"] == "PASS_AS_SANITIZED_REVIEW_CANDIDATE_MANIFEST_NOT_ADMISSION"
    assert audit["manifest_rows"] == 3975
    assert audit["eligible_for_review_rows"] == 2916
    assert audit["quarantined_rows"] == 1059
    assert audit["excluded_reference_source_rows"] == 423
    assert audit["source_target_visible_quarantined_rows"] == 750
    assert audit["trainer_consumable_rows"] == 0
    assert audit["row_admitted_count"] == 0
    assert audit["nonzero_loss_weight_rows"] == 0
    assert audit["candidate_status_counts"] == stage.EXPECTED_STATUS_COUNTS
    assert len(rows) == 6
    assert {row["status"] for row in rows} == {"pass", "blocked"}


def test_review_records_remaining_dataset_blockers() -> None:
    loaded = stage.load_inputs()
    audit, rows = stage.review_manifest(loaded["manifest"], loaded["excluded"])
    assert audit["canonical_split_counts"] == {"train_candidate": 3975}
    assert audit["rows_missing_repo_or_language_metadata_before_admission"] == 3191
    assert audit["remaining_blockers"] == list(stage.REQUIRED_BLOCKERS)
    blocked = [row for row in rows if row["status"] == "blocked"]
    assert [row["check_id"] for row in blocked] == ["split_readiness", "metadata_enrichment", "label_review"]


def test_private_manifest_has_no_forbidden_leaks() -> None:
    loaded = stage.load_inputs()
    stage.assert_no_forbidden(loaded["manifest"], "manifest", stage.PRIVATE_FORBIDDEN_SUBSTRINGS)
    encoded = json.dumps(loaded["manifest"], sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded


def test_build_packet_keeps_all_authority_gates_closed() -> None:
    summary, audit, review_rows = stage.build_packet()
    assert summary["stage12658_manifest_independently_reviewed"] is True
    assert summary["sanitized_manifest_safe_to_use_as_review_input"] is True
    assert summary["structured_repo_state_admission_manifest_allowed_next"] is False
    assert summary["next_required_action"] == "stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only"
    assert audit["next_required_action"] == summary["next_required_action"]
    assert len(review_rows) == 6
    assert_false_boundaries(summary)
    assert_false_boundaries(audit)


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
        "private/review_checks.jsonl",
        "private/structured_repo_state_manifest_review_packet.json",
        "review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_manifest_review_packet.json")
    audit = read_json(out / "review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["review_audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/review_checks.jsonl").open()) == 6


def test_generated_artifacts_match_current_review() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "review_audit.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["structured_repo_state_rows_admitted"] is False
    assert audit["review_decision"] == summary["decision"]
    assert_false_boundaries(summary)
    assert_false_boundaries(audit)
