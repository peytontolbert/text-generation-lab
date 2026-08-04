from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12675_real_repo_knowledge_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12675", SCRIPT)
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


def test_load_inputs_pins_stage12674_materialization() -> None:
    summary74, audit74, contract74, rows, repos = stage.load_inputs()
    assert summary74["materialized_knowledge_rows"] == 31469
    assert audit74["recommended_next_stage"] == stage.STAGE
    assert contract74["materialized_knowledge_rows"] == 31469
    assert len(rows) == 31469
    assert len(repos) == 500


def test_review_rows_finds_no_hard_failures() -> None:
    _, _, _, rows, repos = stage.load_inputs()
    review = stage.review_rows(rows, repos)
    assert review["materialized_knowledge_rows_reviewed"] == 31469
    assert review["repository_metadata_rows_cross_checked"] == 500
    assert review["objective_counts"] == stage.EXPECTED_OBJECTIVE_COUNTS
    assert review["split_counts"] == stage.EXPECTED_SPLIT_COUNTS
    assert review["exact_duplicate_rows"] == 0
    assert review["semantic_duplicate_rows"] == 0
    assert review["cross_split_repo_leakage_groups"] == 0
    assert review["split_mismatch_rows"] == 0
    assert review["authority_open_rows"] == 0
    assert review["bad_evidence_rows"] == 0
    assert review["forbidden_marker_rows"] == 0
    assert review["missing_family_split_pairs"] == 0
    assert review["label_shape_invalid_rows"] == 0
    assert review["target_duplicate_instances"] == 29517
    assert review["target_duplicate_signatures"] == 887
    assert review["target_duplicate_signatures_cross_split"] == 719


def test_build_packet_passes_review_but_keeps_training_blocked() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "BLOCKED_KNOWLEDGE_TRAINING_ADMISSION_REQUIRES_SHORTCUT_AND_ADAPTER_REVIEW"
    assert summary["materialization_review_passed"] is True
    assert summary["training_admission_review_passed"] is False
    assert summary["materialized_knowledge_rows_reviewed"] == 31469
    assert summary["training_source_rows_admitted"] == 0
    assert summary["target_duplicate_instances"] == 29517
    assert summary["target_duplicate_signatures_cross_split"] == 719
    assert summary["trainer_adapter_required"] is True
    assert summary["shortcut_baseline_required"] is True
    assert audit["trainer_adapter_fit"] == "blocked_pending_repo_knowledge_adapter_binding"
    assert audit["shortcut_baseline_status"] == "blocked_pending_objective_family_shortcut_baselines"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "target_duplicate_shortcut_risk",
        "trainer_adapter_binding",
        "shortcut_baseline_materialization",
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
        "digest_pointer.json",
        "private/real_repo_knowledge_independent_review_checks.jsonl",
        "private/real_repo_knowledge_independent_review_packet.json",
        "real_repo_knowledge_independent_review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/real_repo_knowledge_independent_review_packet.json")
    audit = read_json(out / "real_repo_knowledge_independent_review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/real_repo_knowledge_independent_review_checks.jsonl").open()) == 10


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "real_repo_knowledge_independent_review_audit.json")
    assert summary == external
    assert summary["materialized_knowledge_rows_reviewed"] == 31469
    assert summary["materialization_review_passed"] is True
    assert summary["training_admission_review_passed"] is False
    assert summary["training_source_rows_admitted"] == 0
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
