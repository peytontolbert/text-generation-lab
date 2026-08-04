import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12653_repo_code_training_run_authorization_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12653", SCRIPT)
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
    "private/repo_code_training_run_authorization_preflight.json",
    "summary.json",
]


def test_load_inputs_pins_stage12652_and_manifest():
    loaded = stage.load_inputs()
    assert loaded["summary"] == read_json(stage.S12652_SUMMARY)
    assert len(loaded["manifest"]) == 280
    assert stable(loaded["manifest"]) == stage.EXPECTED_HASHES["stage12651_manifest_semantic"]


def test_curriculum_readiness_audit_is_candidate_only_and_gpu_scoped():
    audit = stage.audit_curriculum_readiness(stage.load_inputs())
    assert audit["train_rows_available"] == 153
    assert audit["eval_rows_reserved"] == 64
    assert audit["strict_eval_rows_reserved_not_admitted"] == 63
    assert audit["curriculum_lane_counts"] == stage.EXPECTED_LANES
    run_contract = audit["optimizer_run_contract"]
    assert run_contract["cuda_visible_devices_required"] == "2"
    assert run_contract["forbidden_gpu_ids"] == ["0", "1"]
    assert run_contract["parent_checkpoint"] is None
    assert run_contract["trainer_implementation"] is None
    assert run_contract["optimizer_and_context"] is None


def test_authorization_audit_blocks_training_without_explicit_approval_and_runtime_contract():
    audit = stage.audit_curriculum_readiness(stage.load_inputs())
    assert audit["authorization_blocker_count"] == 6
    assert "explicit_training_authorization_missing" in audit["authorization_blockers"]
    assert "retention_eval_and_shortcut_baseline_plan_not_materialized" in audit["authorization_blockers"]
    assert "cuda2_only_runtime_contract_not_materialized" in audit["authorization_blockers"]
    assert "training_pack_authorization_review_missing" in audit["authorization_blockers"]


def test_packet_materializes_preflight_without_authorizing_training():
    summary, contract, private, pointer = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "BLOCKED_EXPLICIT_TRAINING_AUTHORIZATION_AND_RUNTIME_CONTRACT_REQUIRED"
    assert summary["stage12653_training_run_authorization_preflight_performed"] is True
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["cuda2_training_allowed"] is False
    assert summary["gpu_allocation_requested"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["next_required_action"] == "stage12654_repo_code_training_authorization_independent_review_only"
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["contract_sha256"] == stable(contract)
    for record in (summary, contract, private, pointer):
        assert_false_boundaries(record)


def test_build_writes_preflight_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_preflight():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_training_run_authorization_preflight.json")
    assert summary == external
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_training_text_or_private_paths():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert '"model_input":' not in encoded
        assert '"target_text":' not in encoded
        assert not [needle for needle in stage.FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True


def test_rejects_manifest_gate_or_lane_drift():
    loaded = stage.load_inputs()
    bad_manifest = copy.deepcopy(loaded["manifest"])
    bad_manifest[0]["training_allowed"] = True
    try:
        stage.audit_curriculum_readiness({"summary": loaded["summary"], "manifest": bad_manifest})
    except stage.Stage12653TrainingRunAuthorizationError as exc:
        assert "manifest_gate_drift" in str(exc)
    else:
        raise AssertionError("expected manifest training gate drift rejection")

    bad_manifest = copy.deepcopy(loaded["manifest"])
    bad_manifest[0]["curriculum_lane"] = "repo_graph_and_symbol_binding"
    try:
        stage.audit_curriculum_readiness({"summary": loaded["summary"], "manifest": bad_manifest})
    except stage.Stage12653TrainingRunAuthorizationError as exc:
        assert "lane_count_drift" in str(exc)
    else:
        raise AssertionError("expected lane drift rejection")
