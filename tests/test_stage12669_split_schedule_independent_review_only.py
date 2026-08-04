from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12669_split_schedule_independent_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12669", SCRIPT)
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


def test_load_inputs_pins_stage12668_lanes() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert len(loaded["repo"]) == 200
    assert len(loaded["symbol"]) == 58
    assert len(loaded["structured"]) == 2187


def test_lane_review_counts_losses_and_gates() -> None:
    loaded = stage.load_inputs()
    repo = stage.lane_review("repo_code_decoder_ce", loaded["repo"], expected_mode="bounded_decoder_ce_probe", runnable_candidate=False)
    symbol = stage.lane_review("symbol_binding_probe", loaded["symbol"], expected_mode="symbol_binding_probe", runnable_candidate=True)
    structured = stage.lane_review("structured_repo_state_extension", loaded["structured"], expected_mode="structured_repo_state_probe", runnable_candidate=False)
    assert repo["loss_counts"] == {"decoder_ce": 200}
    assert symbol["loss_counts"] == {"symbol_binding_ce": 58}
    assert structured["loss_counts"] == stage.EXPECTED_LOSSES["structured_repo_state_extension"]
    assert repo["runnable_with_current_trainer_contract_candidate"] is False
    assert symbol["runnable_with_current_trainer_contract_candidate"] is True
    assert structured["runnable_with_current_trainer_contract_candidate"] is False


def test_review_schedule_preserves_blocked_and_candidate_lanes() -> None:
    audit = stage.review_schedule(stage.load_inputs())
    assert audit["review_decision"] == "PASS_SPLIT_SCHEDULE_REVIEW_NO_TRAINING_RUN"
    assert audit["combined_rows_reviewed"] == 2445
    assert audit["current_trainer_candidate_rows"] == 58
    assert audit["repo_code_decoder_target_audit_required_rows"] == 200
    assert audit["trainer_extension_required_rows"] == 2187
    assert audit["structured_duplicate_downweighted_rows_preserved"] == 1686
    assert audit["symbol_binding_action_vocab"] == [
        "ABSTAIN_UNBOUND",
        "BIND_CALL_TO_SYMBOL",
        "BIND_IMPORT_TO_MODULE",
        "BIND_TEST_TO_SYMBOL",
        "RETRIEVE_MORE",
    ]
    assert audit["structured_repo_state_fields"] == ["evidence_role", "evidence_route", "hypothesis_status"]
    assert audit["next_required_action"] == "stage12670_symbol_binding_trainer_contract_validation_preflight_only"
    assert_execution_gates_closed(audit)


def test_build_packet_keeps_training_blocked() -> None:
    summary, audit, checks = stage.build_packet()
    assert summary["decision"] == "PASS_SPLIT_SCHEDULE_REVIEW_NO_TRAINING_RUN"
    assert summary["split_schedule_review_passed"] is True
    assert summary["current_trainer_candidate_rows"] == 58
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["training_admitted"] is False
    assert [row["check_id"] for row in checks if row["status"] == "blocked"] == [
        "repo_code_decoder_lane",
        "structured_repo_state_lane",
        "training_execution_authority",
    ]
    assert audit["next_required_action"] == summary["next_required_action"]
    assert_execution_gates_closed(summary)


def test_public_records_are_sanitized() -> None:
    summary, audit, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)


def test_private_lanes_have_no_forbidden_markers() -> None:
    loaded = stage.load_inputs()
    for label in ("repo", "symbol", "structured"):
        stage.assert_no_forbidden(loaded[label], label, stage.PRIVATE_FORBIDDEN_SUBSTRINGS)


def test_build_writes_review_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/split_schedule_review_checks.jsonl",
        "private/split_schedule_review_packet.json",
        "split_schedule_review_audit.json",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/split_schedule_review_packet.json")
    audit = read_json(out / "split_schedule_review_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["review_audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/split_schedule_review_checks.jsonl").open()) == 5


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "split_schedule_review_audit.json")
    assert summary == external
    assert summary["current_trainer_candidate_rows"] == 58
    assert summary["repo_code_decoder_target_audit_required_rows"] == 200
    assert summary["trainer_extension_required_rows"] == 2187
    assert audit["review_decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
