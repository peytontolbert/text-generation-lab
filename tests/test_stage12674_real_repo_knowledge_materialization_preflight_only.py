from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12674_real_repo_knowledge_materialization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12674", SCRIPT)
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


def test_load_inputs_pins_stage12673_and_repo_universe() -> None:
    upstream, repo_rows = stage.load_inputs()
    assert upstream["current_knowledge_seed_rows"] == 258
    assert upstream["candidate_source_rows_inventory_total"] == 1646
    assert len(repo_rows) == 500


def test_materialize_rows_builds_tens_of_thousands_without_raw_source() -> None:
    _, repo_rows = stage.load_inputs()
    rows = stage.materialize_rows(repo_rows)
    assert len(rows) == 31469
    first = rows[0]
    assert first["row_id"].startswith("stage12674_real_repo_knowledge_")
    assert first["knowledge_input"]["opaque_repo_id"].startswith("repo_")
    assert first["evidence"]["raw_source_included"] is False
    assert first["evidence"]["absolute_path_included"] is False
    assert first["evidence"]["source_body_included"] is False
    stage.assert_no_forbidden(first, "first_row")


def test_summarize_reports_expected_objective_counts_and_closed_authority() -> None:
    upstream, repo_rows = stage.load_inputs()
    rows = stage.materialize_rows(repo_rows)
    summary, audit, checks = stage.summarize(rows, upstream)
    assert summary["decision"] == "REAL_REPO_KNOWLEDGE_ROWS_MATERIALIZED_PRETRAINING_REVIEW_REQUIRED"
    assert summary["materialized_knowledge_rows"] == 31469
    assert summary["objective_counts"] == {
        "build_file_role_fact": 7068,
        "curriculum_use_presence": 3937,
        "extension_count_fact": 9081,
        "language_count_fact": 2236,
        "primary_language_rank_fact": 1774,
        "readme_doc_surface_fact": 4873,
        "repo_capability_profile": 500,
        "repo_health_bucket_fact": 2000,
    }
    assert audit["duplicate_row_hashes"] == 0
    assert audit["authority_open_rows"] == 0
    assert audit["template_marker_or_forbidden_hits"] == 0
    assert audit["raw_source_body_rows"] == 0
    assert audit["absolute_path_rows"] == 0
    assert audit["training_source_rows_admitted"] == 0
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == ["independent_training_admission"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    upstream, repo_rows = stage.load_inputs()
    rows = stage.materialize_rows(repo_rows)
    summary, audit, checks = stage.summarize(rows, upstream)
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
        "digest_pointer.json",
        "private/real_repo_knowledge_materialization_checks.jsonl",
        "private/real_repo_knowledge_materialization_packet.json",
        "real_repo_knowledge_examples.jsonl",
        "real_repo_knowledge_materialization_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/real_repo_knowledge_materialization_packet.json")
    audit = read_json(out / "real_repo_knowledge_materialization_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "real_repo_knowledge_examples.jsonl").open()) == 31469
    assert sum(1 for _ in (out / "private/real_repo_knowledge_materialization_checks.jsonl").open()) == 8


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "real_repo_knowledge_materialization_audit.json")
    assert summary == external
    assert summary["materialized_knowledge_rows"] == 31469
    assert summary["training_source_rows_admitted"] == 0
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
