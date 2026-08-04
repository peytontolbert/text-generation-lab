from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12663_structured_repo_state_training_admission_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12663", SCRIPT)
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


def test_load_inputs_pins_stage12662_preflight() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["manifest"]) == 2187


def test_review_manifest_passes_training_admission_preflight() -> None:
    audit = stage.review_manifest(stage.load_inputs()["manifest"])
    assert audit["review_decision"] == "PASS_STRUCTURED_REPO_STATE_TRAINING_ADMISSION_PREFLIGHT_NO_TRAINING_RUN"
    assert audit["manifest_rows_reviewed"] == 2187
    assert audit["trainer_consumable_rows_reviewed"] == 2187
    assert audit["split_counts"] == stage.EXPECTED_SPLITS
    assert audit["objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["stable_candidate_id_scan_passed"] is True
    assert audit["repo_code_pack_merge_required_before_combined_curriculum"] is True
    assert_execution_gates_closed(audit)


def test_duplicate_signature_downweight_policy_is_recomputed() -> None:
    audit = stage.review_manifest(stage.load_inputs()["manifest"])
    assert audit["cross_split_duplicate_compact_signature_groups"] == 254
    assert audit["cross_split_duplicate_compact_signature_rows"] == 1686
    assert audit["downweighted_rows"] == 1686
    assert audit["full_weight_rows"] == 501
    assert audit["duplicate_loss_weight"] == 0.25


def test_private_manifest_has_no_forbidden_leaks() -> None:
    rows = stage.load_inputs()["manifest"]
    encoded = json.dumps(rows, sort_keys=True)
    for needle in stage.PRIVATE_FORBIDDEN_SUBSTRINGS:
        assert needle not in encoded


def test_build_packet_keeps_training_execution_closed() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["structured_repo_state_training_pack_review_passed"] is True
    assert summary["dataset_rows_admitted"] is True
    assert summary["structured_repo_state_rows_admitted"] is True
    assert summary["training_admission_review_passed"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["next_required_action"] == "stage12664_repo_code_and_structured_state_pack_composition_preflight_only"
    assert audit["next_required_action"] == summary["next_required_action"]
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == ["combined_pack_composition"]
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
        "private/review_checks.jsonl",
        "private/structured_repo_state_training_admission_review_packet.json",
        "review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/structured_repo_state_training_admission_review_packet.json")
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
    assert summary["training_allowed"] is False
    assert summary["manifest_rows_reviewed"] == 2187
    assert audit["review_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
