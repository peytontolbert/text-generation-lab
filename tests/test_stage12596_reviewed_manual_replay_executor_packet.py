import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12596_reviewed_manual_replay_executor_packet.py"
SPEC = importlib.util.spec_from_file_location("stage12596", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def copy_tree(src: Path, dst: Path):
    for path in src.rglob("*"):
        if path.is_file():
            target = dst / path.relative_to(src)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def copy_stage12595(tmp_path: Path):
    dst = tmp_path / "stage12595"
    copy_tree(stage.S12595, dst)
    external = tmp_path / "stage12595_summary.json"
    external.write_bytes(stage.S12595_EXTERNAL.read_bytes())
    return dst, external


def copy_stage12594(tmp_path: Path):
    dst = tmp_path / "stage12594"
    copy_tree(stage.S12594, dst)
    return dst


def assert_false_boundaries(record):
    for field in (
        "authorizes_execution", "execution_allowed", "execution_performed", "replay_trustworthy",
        "level_3_materialized", "training_admitted", "strict_eval_admitted", "sealed_eval_admitted",
        "strict_eval_eligible", "sealed_eval_eligible", "admission_allowed", "training_allowed",
        "ranking_allowed", "positive_stop",
    ):
        assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12594_requires_current_publication_and_pinned_snapshot():
    loaded = stage.load_stage12594()
    assert loaded["summary"]["decision"] == "BLOCKED_TRUSTED_REPLAY_NOT_EXECUTED"
    assert loaded["manifest"]["manifest_sha256"] == stage.EXPECTED_STAGE12594_MANIFEST
    assert loaded["leak"]["passed"] is True
    assert [row["binding_payload_sha256"] for row in loaded["snapshot"]["binding_snapshots"]] == list(stage.EXPECTED_BINDINGS)
    assert_false_boundaries(loaded["summary"])
    assert_false_boundaries(loaded["contract"])


def test_load_stage12594_rejects_manifest_digest_drift(tmp_path):
    root = copy_stage12594(tmp_path)
    manifest = read_json(root / "publication_manifest.json")
    manifest["manifest_sha256"] = "0" * 64
    (root / "publication_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12594_manifest_pin_drift"):
        stage.load_stage12594(root)


def test_load_stage12595_requires_current_non_authorizing_handoff():
    loaded = stage.load_stage12595()
    assert loaded["summary"]["decision"] == "BLOCKED_MANUAL_TRUSTED_REPLAY_EXECUTION_REQUIRED"
    assert loaded["summary"]["execution_request_ready_count"] == 0
    assert loaded["summary"]["stage12596_allowed"] is False
    assert loaded["plan"]["slots_sha256"] == stage.EXPECTED_STAGE12595_SLOT_SHA256
    assert [row["binding_payload_sha256"] for row in loaded["slots"]] == list(stage.EXPECTED_BINDINGS)
    assert_false_boundaries(loaded["summary"])
    assert_false_boundaries(loaded["contract"])


def test_load_stage12595_rejects_execution_request_drift(tmp_path):
    root, external = copy_stage12595(tmp_path)
    summary = read_json(root / "summary.json")
    summary["execution_request_ready_count"] = 2
    (root / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    external.write_text(json.dumps(summary), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12595_count_boundary_mismatch"):
        stage.load_stage12595(root, external)


def test_load_stage12595_rejects_private_handoff_digest_drift(tmp_path):
    root, external = copy_stage12595(tmp_path)
    pointer = read_json(root / "digest_pointer.json")
    pointer["private_handoff_sha256"] = "0" * 64
    (root / "digest_pointer.json").write_text(json.dumps(pointer), encoding="utf-8")
    with pytest.raises(stage.GateError, match="stage12595_private_handoff_digest_mismatch"):
        stage.load_stage12595(root, external)


def test_build_executor_packet_is_reviewed_contract_only():
    loaded94 = stage.load_stage12594()
    loaded95 = stage.load_stage12595()
    summary, slots, bundle = stage.build_executor_packet(loaded94, loaded95)
    assert summary["decision"] == "BLOCKED_TRUSTED_REPLAY_EXECUTION_NOT_PERFORMED"
    assert summary["executor_source_contract_present"] is True
    assert summary["executable_runner_present"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["executor_contract_review_intake_present"] is True
    assert summary["execution_request_ready_count"] == 0
    assert summary["stage12597_allowed"] is False
    assert "separate_manual_executor_source_not_implemented" in summary["downstream_blockers"]
    assert "training_admission_forbidden" in summary["downstream_blockers"]
    assert_false_boundaries(summary)
    assert_public_sanitized(summary)
    assert len(slots) == 2
    assert [row["binding_payload_sha256"] for row in slots] == list(stage.EXPECTED_BINDINGS)
    for row in slots:
        assert row["required_phase_sequence"] == ["initial", "patched", "final"]
        assert "raw_replay_evidence_private_only" in row["required_publication_controls"]
        assert_false_boundaries(row)
    public_contract = bundle["public_contract"]
    private_contract = bundle["private_packet"]["executor_contract"]
    review = bundle["private_packet"]["review"]
    assert public_contract["this_stage_runs_replay"] is False
    assert public_contract["execution_request_ready_count"] == 0
    assert public_contract["executor_command_manifest_present"] is False
    assert private_contract["executable_runner_present"] is False
    assert private_contract["executor_command_manifest_present"] is False
    assert "actual_executor_source_not_present" in review["review_limits"]
    assert review["review_result"] == "review_intake_packet_created_for_non_executing_executor_contract"
    assert_false_boundaries(public_contract)
    assert_false_boundaries(private_contract)
    assert_false_boundaries(review)
    assert_public_sanitized(public_contract)


def test_build_writes_reviewed_packet_without_execution_or_replay_outputs(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_contract = read_json(out / "private/manual_executor_source_contract.json")
    review = read_json(out / "private/independent_executor_contract_review.json")
    slots = read_jsonl(out / "private/manual_executor_slot_contracts.jsonl")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/independent_executor_contract_review.json",
        "private/manual_executor_slot_contracts.jsonl",
        "private/manual_executor_source_contract.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    assert not any("clone" in name or "repo" in name or "command" in name for name in emitted)
    assert contract["manual_executor_only"] is True
    assert private_contract["execution_not_performed_by_this_stage"] is True
    assert pointer["slot_count"] == 2
    assert pointer["private_executor_contract_sha256"] == stage.stable_hash(private_contract)
    assert pointer["private_review_intake_sha256"] == stage.stable_hash(review)
    assert pointer["private_slot_contracts_sha256"] == stage.stable_hash(slots)
    assert len(slots) == 2
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_contract, review, *slots):
        assert_false_boundaries(record)
