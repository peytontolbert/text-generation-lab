from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12671_symbol_binding_lane_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12671", SCRIPT)
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


def test_load_inputs_pins_stage12670_and_stage_docs() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["audit"]["trainer_contract_card"]["passed"] is True
    assert len(loaded["rows"]) == 58


def test_review_rows_preserves_symbol_binding_contract() -> None:
    row_audit = stage.review_rows(stage.load_inputs()["rows"])
    assert row_audit["rows_reviewed"] == 58
    assert row_audit["split_counts"] == stage.EXPECTED_SPLITS
    assert row_audit["binding_action_counts"] == stage.EXPECTED_ACTIONS
    assert row_audit["enabled_loss_counts"] == {"symbol_binding_ce": 58}
    assert row_audit["identity_binding_present"] is True
    assert row_audit["authority_gates_closed"] is True
    assert row_audit["training_gates_closed"] is True


def test_build_packet_aligns_lane_with_knowledge_stage() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "PASS_SYMBOL_BINDING_KNOWLEDGE_LANE_REVIEW_NO_TRAINING_RUN"
    assert summary["knowledge_stage_alignment"] == "repo_graph_and_symbol_binding"
    assert summary["symbol_binding_rows_reviewed"] == 58
    assert summary["symbol_binding_lane_review_passed"] is True
    assert summary["symbol_binding_lane_training_contract_validated"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["next_required_action"] == "stage12672_knowledge_stage_status_rollup_preflight_only"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == ["training_execution_authority"]
    assert audit["stage_structure_docs_pinned"] is True
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)


def test_private_manifest_has_no_forbidden_markers() -> None:
    stage.assert_no_forbidden(stage.load_inputs()["rows"], "rows", stage.PRIVATE_FORBIDDEN_SUBSTRINGS)


def test_build_writes_review_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/symbol_binding_lane_review_checks.jsonl",
        "private/symbol_binding_lane_review_packet.json",
        "summary.json",
        "symbol_binding_lane_review_audit.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/symbol_binding_lane_review_packet.json")
    audit = read_json(out / "symbol_binding_lane_review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["review_audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/symbol_binding_lane_review_checks.jsonl").open()) == 5


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "symbol_binding_lane_review_audit.json")
    assert summary == external
    assert summary["symbol_binding_rows_reviewed"] == 58
    assert audit["review_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
