import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/build_stage12651_repo_code_curriculum_ingestion_contract_preflight_only.py"
SPEC = importlib.util.spec_from_file_location("stage12651", SCRIPT)
assert SPEC and SPEC.loader
stage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage)


def read_json(path: Path):
    return json.loads(path.read_text())


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def stable(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def assert_false_boundaries(record):
    for field in stage.FALSE_FIELDS:
        assert field in record
        assert record[field] is False


EXPECTED_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_curriculum_ingest_manifest.jsonl",
    "private/repo_code_curriculum_ingestion_contract_packet.json",
    "summary.json",
]


def test_load_inputs_pins_stage12650_and_reviewed_examples():
    loaded = stage.load_inputs()
    assert loaded["summary"] == read_json(stage.S12650_SUMMARY)
    assert loaded["summary"]["training_text_renders_verified"] == 280
    assert len(loaded["examples"]) == 280
    assert stable(loaded["examples"]) == stage.EXPECTED_HASHES["stage12649_examples_semantic"]


def test_ingest_manifest_maps_examples_into_repo_code_knowledge_lanes():
    manifest = stage.build_ingest_manifest(stage.load_inputs())
    assert len(manifest) == 280
    assert stage.split_counts(manifest) == stage.EXPECTED_SPLITS
    assert stage.objective_counts(manifest) == stage.EXPECTED_OBJECTIVES
    assert all(row["curriculum_stage"] == stage.CURRICULUM_STAGE for row in manifest)
    assert sum(1 for row in manifest if row["curriculum_lane"] == "repo_code_knowledge.repo_capability_profile") == 200
    assert sum(1 for row in manifest if row["curriculum_lane"] == "repo_code_knowledge.symbol_reference_prediction") == 80
    assert all(row["trainer_consumable"] is True for row in manifest)
    assert all(row["training_allowed"] is False for row in manifest)
    assert all(row["optimizer_step_authorized"] is False for row in manifest)


def test_ingest_audit_keeps_later_capability_stages_excluded():
    manifest = stage.build_ingest_manifest(stage.load_inputs())
    audit = stage.audit_manifest(manifest)
    assert audit["curriculum_ingestion_contract_materialized"] is True
    assert audit["curriculum_stage"] == "stage_01_repo_and_code_knowledge"
    assert audit["repo_code_curriculum_layer_complete"] is True
    assert audit["trainer_consumable_rows"] == 280
    assert audit["repo_code_ce_ingest_rows"] == 200
    assert audit["symbol_binding_ingest_rows"] == 80
    assert audit["placeholder_ingest_rows"] == 0
    assert audit["raw_path_ingest_rows"] == 0
    assert audit["loss_weight_policy"] == {
        "repo_code_knowledge.repo_capability_profile": 1.0,
        "repo_code_knowledge.symbol_reference_prediction": 0.75,
    }
    assert "bounded_decoder" in audit["excluded_later_stage_lanes"]


def test_packet_materializes_contract_without_authorizing_training():
    summary, contract, private, pointer, manifest = stage.build_packet(stage.load_inputs())
    assert summary["decision"] == "CURRICULUM_INGESTION_CONTRACT_MATERIALIZED_NO_TRAINING"
    assert summary["curriculum_ingestion_contract_materialized"] is True
    assert summary["trainer_consumable_rows"] == 280
    assert summary["training_allowed"] is False
    assert summary["training_run_allowed"] is False
    assert summary["optimizer_step_authorized"] is False
    assert summary["strict_eval_admitted"] is False
    assert summary["sealed_eval_admitted"] is False
    assert summary["level_3_materialized"] is False
    assert summary["next_required_action"] == "stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only"
    assert summary["ingest_manifest_sha256"] == stable(manifest)
    assert contract["private_packet_sha256"] == stable(private)
    assert pointer["contract_sha256"] == stable(contract)
    for record in (summary, contract, private, pointer):
        assert_false_boundaries(record)


def test_build_writes_curriculum_ingestion_artifacts(tmp_path):
    out = tmp_path / "artifacts" / stage.STAGE
    summary_path = tmp_path / "summaries" / f"{stage.STAGE}.json"
    summary = stage.build(out, summary_path)
    emitted = sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    assert summary == read_json(summary_path)
    assert summary == read_json(out / "summary.json")
    manifest = read_jsonl(out / "private/repo_code_curriculum_ingest_manifest.jsonl")
    assert len(manifest) == 280
    assert stable(manifest) == summary["ingest_manifest_sha256"]


def test_generated_artifacts_match_current_ingestion_contract():
    emitted = sorted(path.relative_to(stage.OUT).as_posix() for path in stage.OUT.rglob("*") if path.is_file())
    assert emitted == EXPECTED_ARTIFACTS
    summary = read_json(stage.OUT / "summary.json")
    external = read_json(stage.SUMMARY)
    contract = read_json(stage.OUT / "contract.json")
    pointer = read_json(stage.OUT / "digest_pointer.json")
    private = read_json(stage.OUT / "private/repo_code_curriculum_ingestion_contract_packet.json")
    manifest = read_jsonl(stage.OUT / "private/repo_code_curriculum_ingest_manifest.jsonl")
    assert summary == external
    assert summary["training_allowed"] is False
    assert summary["ingest_manifest_sha256"] == stable(manifest)
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
        assert not [needle for needle in stage.PUBLIC_FORBIDDEN_SUBSTRINGS if needle in encoded]
        assert record.get("training_allowed") is not True
        assert record.get("training_run_allowed") is not True
        assert record.get("optimizer_step_authorized") is not True


def test_ingestion_rejects_unknown_objective_or_training_gate_drift():
    loaded = stage.load_inputs()
    bad = copy.deepcopy(loaded)
    bad["examples"][0]["training_objective"] = "bounded_decoder_ce"
    try:
        stage.build_ingest_manifest(bad)
    except stage.Stage12651IngestionContractError as exc:
        assert "example_split_or_objective_drift" in str(exc) or "unknown_training_objective" in str(exc)
    else:
        raise AssertionError("expected unknown objective rejection")

    bad = copy.deepcopy(loaded)
    bad["examples"][0]["training_allowed"] = True
    try:
        stage.build_ingest_manifest(bad)
    except stage.Stage12651IngestionContractError as exc:
        assert "example_gate_or_optimizer_marker_drift" in str(exc)
    else:
        raise AssertionError("expected training gate drift rejection")
