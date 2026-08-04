import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12648_separate_training_admission_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12648", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/separate_training_admission_preflight_only.json",
    "summary.json",
]


def test_load_stage12647_pins_completion_artifacts_and_admitted_rows():
    loaded = stage.load_stage12647()
    assert loaded["summary"] == read_json(stage.S12647_SUMMARY)
    assert loaded["summary"]["repo_code_knowledge_stage_complete"] is True
    assert loaded["summary"]["dataset_rows_admitted"] is True
    assert len(loaded["admitted"]) == 280


def test_training_admission_blocks_hash_only_non_trainable_ledger():
    audit = stage.audit_training_admission(stage.load_stage12647())
    assert audit["repo_code_knowledge_stage_complete"] is True
    assert audit["dataset_rows_admitted"] is True
    assert audit["repo_code_knowledge_rows_admitted"] == 280
    assert audit["hash_only_admitted_rows"] == 280
    assert audit["model_ready_training_rows"] == 0
    assert audit["training_admission_decision"] == "BLOCKED_TRAINING_PACK_MATERIALIZATION_REQUIRED"
    assert "admitted_curriculum_ledger_is_hash_only_not_trainable_text" in audit["training_blockers"]
    assert "repo_code_training_pack_not_materialized" in audit["training_blockers"]


def test_packet_keeps_training_eval_level3_gpu_vm_closed():
    summary, contract, private = stage.build_packet(stage.load_stage12647())
    assert summary["decision"] == "BLOCKED_TRAINING_PACK_MATERIALIZATION_REQUIRED"
    assert summary["repo_code_knowledge_stage_complete"] is True
    assert summary["dataset_rows_admitted"] is True
    assert summary["repo_code_rows_admitted"] is True
    assert summary["repo_code_knowledge_rows_admitted"] == 280
    assert summary["model_ready_training_rows"] == 0
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["vm_runner_execution_allowed"] is False
    assert summary["next_required_action"] == "stage12649_repo_code_training_pack_materialization_preflight_only"
    assert contract["private_packet_sha256"] == stable(private)
    for record in (summary, contract, private):
        assert_false_boundaries(record)


def test_build_writes_training_admission_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_training_admission_preflight():
    out = stage.OUT
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(out / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(out / "contract.json")
    pointer = read_json(out / "digest_pointer.json")
    private = read_json(out / "private/separate_training_admission_preflight_only.json")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["model_ready_training_rows"] == 0
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    assert pointer["training_admission_audit_sha256"] == stable(private["training_admission_audit"])
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_private_leaks_or_training_authority():
    public_paths = [
        stage.OUT / "summary.json",
        stage.SUMMARY,
        stage.OUT / "contract.json",
        stage.OUT / "digest_pointer.json",
    ]
    for path in public_paths:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("training_run_allowed") is not True
        assert record.get("strict_eval_admitted") is not True
        assert record.get("sealed_eval_admitted") is not True
        assert record.get("level_3_materialized") is not True


def test_training_admission_rejects_incomplete_or_non_hash_only_regressions():
    loaded = stage.load_stage12647()
    incomplete = copy.deepcopy(loaded)
    incomplete["summary"]["repo_code_knowledge_stage_complete"] = False
    try:
        stage.audit_training_admission(incomplete)
    except stage.Stage12648TrainingAdmissionError as exc:
        assert "repo_code_stage_not_complete" in str(exc)
    else:
        raise AssertionError("expected incomplete repo/code stage rejection")

    leaky = copy.deepcopy(loaded)
    leaky["admitted"][0]["debug_path"] = "/arxiv/repositories/leak"
    try:
        stage.audit_training_admission(leaky)
    except stage.Stage12648TrainingAdmissionError as exc:
        assert "admitted_row_not_hash_only" in str(exc)
    else:
        raise AssertionError("expected non-hash-only admitted row rejection")
