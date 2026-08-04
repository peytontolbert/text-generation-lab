from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12672_knowledge_stage_status_rollup_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12672", SCRIPT)
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


def test_load_inputs_pins_knowledge_stage_sources() -> None:
    loaded = stage.load_inputs()
    assert loaded["stage12671_summary"]["next_required_action"] == stage.STAGE
    assert loaded["stage12671_summary"]["symbol_binding_rows_reviewed"] == 58
    assert loaded["stage12665_summary"]["combined_trainer_rows_reviewed"] == 2445


def test_build_packet_rolls_up_knowledge_stage_without_training() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "KNOWLEDGE_STAGE_ROLLUP_COMPLETE_NO_TRAINING_RUN"
    assert summary["repo_code_knowledge_stage_complete"] is True
    assert summary["knowledge_stage_rows_reviewed"] == 258
    assert summary["symbol_binding_rows_contract_validated"] == 58
    assert summary["repo_code_decoder_target_audit_required_rows"] == 200
    assert summary["structured_repo_state_extension_required_rows"] == 2187
    assert summary["symbol_binding_knowledge_lane_ready_for_training_admission_review"] is True
    assert summary["next_required_action"] == "stage12673_symbol_binding_training_admission_review_only"
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "repo_decoder_target_audit",
        "structured_repo_state_trainer_extension",
        "training_execution_authority",
    ]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_lane_status_preserves_stage_boundaries() -> None:
    _, audit, _ = stage.build_packet()
    lanes = {row["lane"]: row for row in audit["lane_status"]}
    assert lanes["repo_code_capability_profile"]["training_stage"] == "repo_and_code_knowledge"
    assert lanes["source_backed_symbol_binding"]["training_stage"] == "repo_graph_and_symbol_binding"
    assert lanes["structured_repo_state"]["training_stage"] == "structured_repo_state"
    assert lanes["source_backed_symbol_binding"]["status"] == "knowledge_lane_reviewed_and_trainer_contract_validated"
    assert lanes["structured_repo_state"]["remaining_blocker"] == "structured_loss_head_and_validator_registration"


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label)


def test_build_writes_rollup_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "knowledge_stage_status_rollup_audit.json",
        "private/knowledge_stage_status_rollup_checks.jsonl",
        "private/knowledge_stage_status_rollup_packet.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/knowledge_stage_status_rollup_packet.json")
    audit = read_json(out / "knowledge_stage_status_rollup_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["rollup_audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/knowledge_stage_status_rollup_checks.jsonl").open()) == 6


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "knowledge_stage_status_rollup_audit.json")
    assert summary == external
    assert summary["knowledge_stage_rows_reviewed"] == 258
    assert audit["rollup_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
