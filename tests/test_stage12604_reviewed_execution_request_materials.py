import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12604_reviewed_execution_request_materials.py"
SPEC = importlib.util.spec_from_file_location("stage12604", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def assert_false_boundaries(record, require_all=True):
    for field in (
        "implementation_ready", "stage12595_allowed", "authorizes_execution", "execution_allowed",
        "execution_performed", "replay_trustworthy", "level_3_materialized", "training_admitted",
        "strict_eval_admitted", "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible",
        "admission_allowed", "training_allowed", "ranking_allowed", "positive_stop",
    ):
        if require_all or field in record:
            assert record[field] is False


def assert_public_sanitized(record):
    encoded = json.dumps(record, sort_keys=True)
    for forbidden in stage.PUBLIC_FORBIDDEN_SUBSTRINGS:
        assert forbidden not in encoded


def test_load_stage12603_requires_review_pass_but_no_execution_gate():
    loaded = stage.load_stage12603()
    summary = loaded["summary"]
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_REQUIRED"
    assert summary["reviewed_execution_capable_source_present"] is True
    assert summary["independent_execution_capable_source_review_passed"] is True
    assert summary["execute_path_enabled"] is False
    assert summary["execution_gate_granted"] is False
    assert summary["execution_request_ready_count"] == 0
    assert summary["this_stage_runs_replay"] is False
    assert summary["executor_command_manifest_present"] is False
    assert summary["raw_replay_evidence_present"] is False
    for record in loaded.values():
        assert_false_boundaries(record)


def test_materialize_patch_files_derives_expected_private_patch_material(tmp_path):
    patch_root = tmp_path / "patches"
    records = stage.materialize_patch_files(patch_root)
    assert [record["slot_ordinal"] for record in records] == [1, 2]
    expected = {
        1: ("slot_1.patch", "59dafa5032f5faf18ed603d96718ab6e1538f9021ba487fe20ac32650400f0dc", 21683),
        2: ("slot_2.patch", "dce96a116a9d07f4076c175ce7d2a68a95c5b2cd0f43d03daa23581a12d95029", 786),
    }
    for record in records:
        name, digest, byte_count = expected[record["slot_ordinal"]]
        patch = patch_root / name
        assert patch.is_file()
        assert stage.sha256_file(patch) == digest
        assert patch.stat().st_size == byte_count
        assert record["patch_file"] == name
        assert record["patch_sha256"] == digest
        assert record["patch_byte_count"] == byte_count
        assert patch.read_bytes().startswith(b"diff --git ")
        assert_false_boundaries(record)


def test_build_private_materials_creates_command_manifest_without_execution(tmp_path):
    private_request, command_manifest = stage.build_private_materials(tmp_path / stage.STAGE)
    assert private_request["patch_material_count"] == 2
    assert private_request["execution_request_ready_count"] == 2
    assert private_request["execution_gate_granted"] is False
    assert private_request["execute_path_enabled"] is False
    assert private_request["this_stage_runs_replay"] is False
    assert private_request["raw_replay_evidence_present"] is False
    assert private_request["executor_command_manifest_sha256"] == stage.stable_hash(command_manifest)
    assert command_manifest["record_type"] == "stage12602_candidate_execution_command_manifest_v1"
    assert command_manifest["slot_count"] == 2
    assert len(command_manifest["slots"]) == 2
    assert all(slot["phase_sequence"] == ["initial", "patched", "final"] for slot in command_manifest["slots"])
    assert all(set(slot["phase_commands"]) == {"initial", "patched", "final"} for slot in command_manifest["slots"])
    assert not (tmp_path / stage.STAGE / "private/future_evidence_root").exists()
    assert_false_boundaries(private_request)


def test_build_public_packet_keeps_gate_closed_and_public_sanitized(tmp_path):
    private_request, command_manifest = stage.build_private_materials(tmp_path / stage.STAGE)
    summary, contract = stage.build_public_packet(private_request, command_manifest)
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_GRANT_REQUIRED"
    assert summary["execution_request_materials_present"] is True
    assert summary["patch_material_count"] == 2
    assert summary["executor_command_manifest_present"] is True
    assert summary["execution_request_ready_count"] == 2
    assert summary["execution_gate_granted"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["this_stage_runs_replay"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12605_allowed"] is False
    assert "execution_gate_not_granted_for_reviewed_source" in summary["downstream_blockers"]
    assert contract["executor_command_manifest_sha256"] == summary["executor_command_manifest_sha256"]
    for record in (summary, contract):
        assert_false_boundaries(record)
        assert_public_sanitized(record)


def test_build_writes_reviewed_execution_request_materials_without_replay(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == [
        "contract.json",
        "digest_pointer.json",
        "private/executor_command_manifest.json",
        "private/patch_material_records.json",
        "private/patches/slot_1.patch",
        "private/patches/slot_2.patch",
        "private/reviewed_execution_request_materials.json",
        "summary.json",
    ]
    assert not any("stdout.raw" in name or "stderr.raw" in name or "pytest" in name for name in emitted)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_request = read_json(out / "private/reviewed_execution_request_materials.json")
    command_manifest = read_json(out / "private/executor_command_manifest.json")
    patch_records = read_json(out / "private/patch_material_records.json")
    assert pointer["private_reviewed_execution_request_materials_sha256"] == stage.stable_hash(private_request)
    assert pointer["private_executor_command_manifest_sha256"] == stage.stable_hash(command_manifest)
    assert pointer["private_patch_material_records_sha256"] == private_request["patch_material_records_sha256"]
    assert private_request["patch_material_records_sha256"] == stage.stable_hash(patch_records["records"])
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_request, patch_records):
        assert_false_boundaries(record)


def test_generated_stage12604_artifacts_match_current_material_boundary():
    out = stage.OUT
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private_request = read_json(out / "private/reviewed_execution_request_materials.json")
    command_manifest = read_json(out / "private/executor_command_manifest.json")
    patch_records = read_json(out / "private/patch_material_records.json")
    assert summary == external
    assert summary["decision"] == "BLOCKED_EXECUTION_GATE_GRANT_REQUIRED"
    assert summary["execution_request_materials_present"] is True
    assert summary["patch_material_count"] == 2
    assert summary["executor_command_manifest_present"] is True
    assert summary["execution_request_ready_count"] == 2
    assert summary["execution_gate_granted"] is False
    assert summary["execute_path_enabled"] is False
    assert summary["execution_allowed"] is False
    assert summary["execution_performed"] is False
    assert summary["raw_replay_evidence_present"] is False
    assert summary["stage12605_allowed"] is False
    assert pointer["private_reviewed_execution_request_materials_sha256"] == stage.stable_hash(private_request)
    assert pointer["private_executor_command_manifest_sha256"] == stage.stable_hash(command_manifest)
    assert command_manifest["slot_count"] == 2
    assert patch_records["records"][0]["patch_sha256"] == "59dafa5032f5faf18ed603d96718ab6e1538f9021ba487fe20ac32650400f0dc"
    assert patch_records["records"][1]["patch_sha256"] == "dce96a116a9d07f4076c175ce7d2a68a95c5b2cd0f43d03daa23581a12d95029"
    assert stage.sha256_file(out / "private/patches/slot_1.patch") == patch_records["records"][0]["patch_sha256"]
    assert stage.sha256_file(out / "private/patches/slot_2.patch") == patch_records["records"][1]["patch_sha256"]
    for public_record in (summary, contract, pointer):
        assert_public_sanitized(public_record)
    for record in (summary, contract, pointer, private_request, patch_records):
        assert_false_boundaries(record)


def test_stage12604_rejects_public_leak_of_private_material():
    leaked = {"production_path": "src/_pytest/_io/pprint.py", **stage.no_claim_fields()}
    with pytest.raises(stage.GateError, match="public_leak"):
        stage.assert_public_sanitized(leaked, "leaked")
