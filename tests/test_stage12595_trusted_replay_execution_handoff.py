import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12595_trusted_replay_execution_handoff.py"
SPEC = importlib.util.spec_from_file_location("stage12595", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def assert_false_boundaries(record):
    for field in (
        "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def test_load_stage12594_requires_current_reviewed_generation():
    loaded = stage.load_stage12594()
    assert loaded["summary"]["decision"] == "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED"
    assert loaded["review"]["review_result"] == "passed_no_blocker_found"
    assert loaded["manifest"]["manifest_sha256"] == stage.EXPECTED_STAGE12594_MANIFEST
    assert_false_boundaries(loaded["summary"])
    assert_false_boundaries(loaded["contract"])


def test_load_stage12594_rejects_generation_drift(monkeypatch, tmp_path):
    src = stage.S12594
    dst = tmp_path / "stage12594"
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    external = tmp_path / "summary.json"
    external.write_bytes(stage.S12594_EXTERNAL.read_bytes())
    summary = read_json(dst / "summary.json")
    summary["publication_generation_id"] = "0" * 64
    (dst / "summary.json").write_text(json.dumps(summary))
    with pytest.raises(stage.GateError, match="stage12594_generation_drift"):
        stage.load_stage12594(dst, external)


def test_build_execution_handoff_is_manual_only_and_preserves_boundaries():
    loaded = stage.load_stage12594()
    summary, slots, bundle = stage.build_execution_handoff(loaded)
    assert summary["decision"] == "BLOCKED_MANUAL_TRUSTED_REPLAY_EXECUTION_REQUIRED"
    assert summary["manual_replay_slot_count"] == 2
    assert summary["execution_request_ready_count"] == 0
    assert summary["execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["stage12596_allowed"] is False
    assert "manual_replay_execution_not_performed" in summary["downstream_blockers"]
    assert "level3_materialization_forbidden" in summary["downstream_blockers"]
    assert_false_boundaries(summary)
    assert len(slots) == 2
    assert [row["binding_payload_sha256"] for row in slots] == list(stage.EXPECTED_BINDINGS)
    for row in slots:
        assert "run_initial_patched_final_phases_inside_hardened_bwrap" in row["manual_executor_required_controls"]
        assert_false_boundaries(row)
    contract = bundle["public_contract"]
    assert contract["manual_executor_only"] is True
    assert contract["this_stage_runs_replay"] is False
    assert contract["execution_request_ready_count"] == 0
    assert contract["claim_boundary"]["training_admission"] == "separate_future_gate_required"
    assert_false_boundaries(contract)


def test_build_writes_public_and_private_handoff_without_replay(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    plan = read_json(out / "private/manual_replay_execution_handoff.json")
    slots = read_jsonl(out / "private/manual_replay_execution_slots.jsonl")
    assert contract["executor_source_in_this_stage"] is False
    assert pointer["slot_count"] == 2
    assert plan["execution_not_performed_by_this_stage"] is True
    assert len(slots) == 2
    for record in (summary, contract, pointer, plan, *slots):
        assert_false_boundaries(record)
