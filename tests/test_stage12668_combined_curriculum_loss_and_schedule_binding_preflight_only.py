from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12668_combined_curriculum_loss_and_schedule_binding_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12668", SCRIPT)
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


def test_load_inputs_pins_stage12667_adapter() -> None:
    loaded = stage.load_inputs()
    assert loaded["summary"]["next_required_action"] == stage.STAGE
    assert loaded["summary"]["training_allowed"] is False
    assert len(loaded["rows"]) == 2445


def test_split_lanes_materializes_expected_counts_and_modes() -> None:
    rows = stage.load_inputs()["rows"]
    repo, symbol, structured, matrix = stage.split_lanes(rows)
    assert len(repo) == 200
    assert len(symbol) == 58
    assert len(structured) == 2187
    assert matrix["current_trainer_candidate_rows"] == 58
    assert matrix["decoder_target_audit_required_rows"] == 200
    assert matrix["trainer_extension_required_rows"] == 2187
    assert matrix["structured_duplicate_downweighted_rows_preserved"] == 1686
    assert repo[0]["trainer_mode_candidate"] == "bounded_decoder_ce_probe"
    assert symbol[0]["trainer_mode_candidate"] == "symbol_binding_probe"
    assert structured[0]["trainer_mode_candidate"] == "structured_repo_state_probe"


def test_repo_lane_remaps_repo_code_ce_to_decoder_ce_only() -> None:
    repo, _, _, _ = stage.split_lanes(stage.load_inputs()["rows"])
    assert stage.count(repo, "split") == stage.EXPECTED_LANE_SPLITS["repo_code_decoder_ce"]
    assert {tuple(k for k, v in row["loss_mask"].items() if v) for row in repo} == {("decoder_ce",)}
    assert all(row["target"]["decoder_text"].strip() for row in repo)
    assert all(row["training_allowed"] is False for row in repo)


def test_symbol_lane_parses_binding_action_for_existing_structured_probe() -> None:
    _, symbol, _, _ = stage.split_lanes(stage.load_inputs()["rows"])
    assert stage.count(symbol, "split") == stage.EXPECTED_LANE_SPLITS["symbol_binding_probe"]
    assert {tuple(k for k, v in row["loss_mask"].items() if v) for row in symbol} == {("symbol_binding_ce",)}
    assert all(row["target"]["binding_action"] == row["clean_state"]["binding_action"] for row in symbol)
    assert {row["target"]["binding_action"] for row in symbol} == {
        "ABSTAIN_UNBOUND",
        "BIND_CALL_TO_SYMBOL",
        "BIND_IMPORT_TO_MODULE",
        "BIND_TEST_TO_SYMBOL",
        "RETRIEVE_MORE",
    }


def test_structured_lane_preserves_downweights_and_requires_extension() -> None:
    _, _, structured, matrix = stage.split_lanes(stage.load_inputs()["rows"])
    assert stage.count(structured, "split") == stage.EXPECTED_LANE_SPLITS["structured_repo_state_extension"]
    assert sum(1 for row in structured if row["loss_weight"] == 0.25) == 1686
    assert sum(1 for row in structured if row["loss_weight"] == 1.0) == 501
    assert {row["structured_repo_state_field"] for row in structured} == {"evidence_role", "evidence_route", "hypothesis_status"}
    assert matrix["adapter_manifest_trainer_runnable_as_single_mixed_invocation"] is False


def test_build_packet_keeps_training_blocked() -> None:
    summary, audit, repo, symbol, structured = stage.build_packet()
    assert summary["decision"] == "SPLIT_SCHEDULE_MATERIALIZED_REPO_DECODER_AUDIT_AND_STRUCTURED_EXTENSION_REQUIRED"
    assert summary["repo_code_decoder_candidate_rows"] == len(repo) == 200
    assert summary["repo_code_decoder_target_audit_required_rows"] == 200
    assert summary["current_trainer_candidate_rows"] == 58
    assert summary["symbol_binding_candidate_rows"] == len(symbol) == 58
    assert summary["structured_repo_state_extension_rows"] == len(structured) == 2187
    assert summary["schedule_binding_preflight_passed"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["next_required_action"] == "stage12669_split_schedule_independent_review_only"
    assert audit["authorization_blockers"] == summary["authorization_blockers"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)


def test_public_records_are_sanitized() -> None:
    summary, audit, _, _, _ = stage.build_packet()
    for label, record in (("summary", summary), ("audit", audit)):
        stage.assert_no_forbidden(record, label, stage.PUBLIC_FORBIDDEN_SUBSTRINGS)


def test_private_lane_manifests_have_no_forbidden_markers() -> None:
    _, _, repo, symbol, structured = stage.build_packet()
    for label, rows in (("repo", repo), ("symbol", symbol), ("structured", structured)):
        stage.assert_no_forbidden(rows, label, stage.PRIVATE_FORBIDDEN_SUBSTRINGS)


def test_build_writes_loss_schedule_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "loss_schedule_binding_audit.json",
        "private/loss_schedule_binding_packet.json",
        "private/repo_code_decoder_ce_candidate_manifest.jsonl",
        "private/structured_repo_state_extension_candidate_manifest.jsonl",
        "private/symbol_binding_probe_candidate_manifest.jsonl",
        "summary.json",
    ]
    assert summary == read_json(summary_path)
    pointer = read_json(out / "digest_pointer.json")
    contract = read_json(out / "contract.json")
    private = read_json(out / "private/loss_schedule_binding_packet.json")
    audit = read_json(out / "loss_schedule_binding_audit.json")
    assert pointer["summary_sha256"] == stable(summary)
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["audit_sha256"] == stable(audit)
    assert sum(1 for _ in (out / "private/repo_code_decoder_ce_candidate_manifest.jsonl").open()) == 200
    assert sum(1 for _ in (out / "private/symbol_binding_probe_candidate_manifest.jsonl").open()) == 58
    assert sum(1 for _ in (out / "private/structured_repo_state_extension_candidate_manifest.jsonl").open()) == 2187


def test_generated_artifacts_match_current_stage() -> None:
    stage.build()
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    audit = read_json(stage.OUT / "loss_schedule_binding_audit.json")
    assert summary == external
    assert summary["current_trainer_candidate_rows"] == 58
    assert summary["decoder_target_audit_required_rows"] == 200
    assert summary["trainer_extension_required_rows"] == 2187
    assert audit["decision"] == summary["decision"]
    assert_execution_gates_closed(summary)
    assert_execution_gates_closed(audit)
