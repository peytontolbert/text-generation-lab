import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only.py"
SPEC = importlib.util.spec_from_file_location("stage12652", SCRIPT)
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
    "private/repo_code_curriculum_ingest_manifest_review_packet.json",
    "summary.json",
]


def test_load_inputs_pins_stage12651_manifest_and_examples():
    loaded = stage.load_inputs()
    assert loaded["summary"] == read_json(stage.S12651_SUMMARY)
    assert len(loaded["manifest"]) == 280
    assert len(loaded["examples"]) == 280
    assert stable(loaded["manifest"]) == stage.EXPECTED_HASHES["stage12651_manifest_semantic"]
    assert stable(loaded["examples"]) == stage.EXPECTED_HASHES["stage12649_examples_semantic"]


def test_review_manifest_verifies_source_example_bindings_and_lanes():
    audit = stage.review_manifest(stage.load_inputs())
    assert audit["curriculum_ingest_manifest_review_passed"] is True
    assert audit["source_example_joins_verified"] == 280
    assert audit["source_example_hashes_verified"] == 280
    assert audit["curriculum_lane_counts"] == stage.EXPECTED_LANES
    assert audit["training_split_counts"] == stage.EXPECTED_SPLITS
    assert audit["training_objective_counts"] == stage.EXPECTED_OBJECTIVES
    assert audit["stale_drift_schema_rows"] == 0
    assert audit["review_blocker_count"] == 0


def test_packet_reviews_manifest_without_authorizing_training():
    summary, contract, private, pointer = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "CURRICULUM_INGEST_MANIFEST_REVIEW_PASSED_NO_TRAINING"
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["next_required_action"] == "stage12653_repo_code_training_run_authorization_preflight_only"
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["contract_sha256"] == stable(contract)
    for record in (summary, contract, private, pointer):
        assert_false_boundaries(record)


def test_build_writes_review_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")


def test_generated_artifacts_match_current_review():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_curriculum_ingest_manifest_review_packet.json")
    assert summary == external
    assert pointer["contract_sha256"] == stable(contract)
    assert pointer["private_packet_sha256"] == stable(private)
    for record in (summary, contract, pointer, private):
        assert_false_boundaries(record)


def test_public_artifacts_have_no_training_text_private_paths_or_drift_schema():
    for path in [stage.OUT / "summary.json", stage.SUMMARY, stage.OUT / "contract.json", stage.OUT / "digest_pointer.json"]:
        record = read_json(path)
        encoded = json.dumps(record, sort_keys=True)
        assert '"model_input":' not in encoded
        assert '"target_text":' not in encoded
        assert not [needle for needle in stage.FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True


def test_review_rejects_stale_schema_or_source_hash_drift():
    loaded = stage.load_inputs()
    bad = copy.deepcopy(loaded)
    bad["manifest"][0]["curriculum_lane"] = "repo_graph_and_symbol_binding"
    try:
        stage.review_manifest(bad)
    except stage.Stage12652ReviewError as exc:
        assert "manifest_lane_count_drift" in str(exc) or "leak_or_drift" in str(exc)
    else:
        raise AssertionError("expected stale schema rejection")

    bad = copy.deepcopy(loaded)
    bad["manifest"][0]["source_example_sha256"] = "0" * 64
    try:
        stage.review_manifest(bad)
    except stage.Stage12652ReviewError as exc:
        assert "source_example_hash_drift" in str(exc)
    else:
        raise AssertionError("expected source example hash drift rejection")


def test_review_rejects_training_gate_or_loss_weight_drift():
    loaded = stage.load_inputs()
    bad = copy.deepcopy(loaded)
    bad["manifest"][0]["training_allowed"] = True
    try:
        stage.review_manifest(bad)
    except stage.Stage12652ReviewError as exc:
        assert "manifest_gate_drift" in str(exc)
    else:
        raise AssertionError("expected training gate drift rejection")

    bad = copy.deepcopy(loaded)
    bad["manifest"][0]["loss_weight"] = 9.0
    try:
        stage.review_manifest(bad)
    except stage.Stage12652ReviewError as exc:
        assert "loss_weight_drift" in str(exc)
    else:
        raise AssertionError("expected loss weight drift rejection")
