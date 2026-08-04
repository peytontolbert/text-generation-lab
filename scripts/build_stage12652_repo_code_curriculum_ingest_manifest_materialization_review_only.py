#!/usr/bin/env python3
# Independently review the repo/code curriculum ingest manifest without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12651 = ROOT / "runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only"
S12651_SUMMARY = ROOT / "runs/summaries/stage12651_repo_code_curriculum_ingestion_contract_preflight_only.json"
S12651_SCRIPT = ROOT / "scripts/build_stage12651_repo_code_curriculum_ingestion_contract_preflight_only.py"
S12651_TESTS = ROOT / "tests/test_stage12651_repo_code_curriculum_ingestion_contract_preflight_only.py"
S12649_EXAMPLES = ROOT / "runs/local/artifacts/stage12649_repo_code_training_pack_materialization_preflight_only/private/repo_code_training_examples.jsonl"

EXPECTED_HASHES = {
    "stage12651_summary": "ccc71e82b6c0e030eb27990ce521c4fbaf94004e609309f8700bada6568459e0",
    "stage12651_contract": "bb14fe1a1b3b0774c98ac58cffa1c69c0ce9b8e1efef0885b805244ead96ea95",
    "stage12651_pointer": "e957e28b709ea8fd70e782efcd8dd3ede47b5c77f93d2919425d532de659efba",
    "stage12651_private_packet": "fb8189c561e59b60ca787de5e02b6336853846502de1bd54f03206a09811d2bd",
    "stage12651_manifest_bytes": "d19e8b0139d1dd179ca369b7db8c4252b8ac4e711855208fd273ec9419a46cb1",
    "stage12651_manifest_semantic": "21b3d427575a7883950600ab93e0980d3f74ad52f146bde58d6eba27144ead79",
    "stage12651_script_bytes": "b4ba5ca35cb9eb734246c93b6d8d789a7e001cc4d908c25e3de564b870342ebf",
    "stage12651_tests_bytes": "b86f18f5a706fa685d1bb3c2827016d3d7ef0c4c4d3cc0dad623db76ebe293c0",
    "stage12649_examples_bytes": "21ec4c4edd027a844042e0d04a4fa7e73611aea503302ecfa37e13dbe170261d",
    "stage12649_examples_semantic": "ab79d922b129853ad76fbdc2121296c0d75478d9f6fdcd28697587d683de62d1",
}
EXPECTED_STAGE12651_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_curriculum_ingest_manifest.jsonl",
    "private/repo_code_curriculum_ingestion_contract_packet.json",
    "summary.json",
]
EXPECTED_COUNTS = {"repo_code_ce": 200, "source_backed_symbol_binding": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
EXPECTED_OBJECTIVES = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
EXPECTED_LANES = {"repo_code_knowledge.repo_capability_profile": 200, "repo_code_knowledge.symbol_reference_prediction": 80}
EXPECTED_WEIGHTS = {"repo_code_knowledge.repo_capability_profile": 1.0, "repo_code_knowledge.symbol_reference_prediction": 0.75}
FALSE_FIELDS = (
    "training_admission_allowed",
    "training_allowed",
    "training_run_allowed",
    "training_admitted",
    "strict_eval_admitted",
    "sealed_eval_admitted",
    "strict_eval_eligible",
    "sealed_eval_eligible",
    "implementation_ready",
    "stage12595_allowed",
    "replay_trustworthy",
    "level_3_materialized",
    "gpu_allocation_requested",
    "cuda2_training_allowed",
    "vm_runner_execution_allowed",
    "runtime_authorized",
    "model_execution_authorized_next",
    "source_emission_authorized",
    "body_emission_authorized",
    "decoder_ce_training_authorized_next",
    "transition_head_training_authorized_next",
    "promotion_ready",
    "optimizer_step_authorized",
)
FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "Answer:",
    "PLACEHOLDER",
    "TODO",
    "TBD",
    "<fill",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "source_lineage",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repo_graph_and_symbol_binding",
)


class Stage12652ReviewError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12652ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12652ReviewError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def false_fields() -> dict[str, bool]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12652ReviewError(f"{label}_gate_drift:{field}")


def assert_no_leaks(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12652ReviewError(f"{label}_leak_or_drift:{needle}")
    if '"model_input":' in encoded or '"target_text":' in encoded:
        raise Stage12652ReviewError(f"{label}_training_text_leak")


def count_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(field)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12651).as_posix() for path in S12651.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12651_ARTIFACTS:
        raise Stage12652ReviewError("stage12651_artifact_manifest_drift")
    summary = read_json(S12651 / "summary.json")
    external = read_json(S12651_SUMMARY)
    contract = read_json(S12651 / "contract.json")
    pointer = read_json(S12651 / "digest_pointer.json")
    private = read_json(S12651 / "private/repo_code_curriculum_ingestion_contract_packet.json")
    manifest_bytes = (S12651 / "private/repo_code_curriculum_ingest_manifest.jsonl").read_bytes()
    examples_bytes = S12649_EXAMPLES.read_bytes()
    manifest = read_jsonl_bytes(manifest_bytes)
    examples = read_jsonl_bytes(examples_bytes)
    if summary != external:
        raise Stage12652ReviewError("stage12651_external_summary_mismatch")
    for label, value in (
        ("stage12651_summary", summary),
        ("stage12651_contract", contract),
        ("stage12651_pointer", pointer),
        ("stage12651_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12652ReviewError("pin_drift:" + label)
    for label, data in (
        ("stage12651_manifest_bytes", manifest_bytes),
        ("stage12651_script_bytes", S12651_SCRIPT.read_bytes()),
        ("stage12651_tests_bytes", S12651_TESTS.read_bytes()),
        ("stage12649_examples_bytes", examples_bytes),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12652ReviewError("pin_drift:" + label)
    if stable_hash(manifest) != EXPECTED_HASHES["stage12651_manifest_semantic"]:
        raise Stage12652ReviewError("pin_drift:stage12651_manifest_semantic")
    if stable_hash(examples) != EXPECTED_HASHES["stage12649_examples_semantic"]:
        raise Stage12652ReviewError("pin_drift:stage12649_examples_semantic")
    if summary.get("decision") != "CURRICULUM_INGESTION_CONTRACT_MATERIALIZED_NO_TRAINING":
        raise Stage12652ReviewError("stage12651_not_ingestion_contract")
    if summary.get("ingest_manifest_sha256") != stable_hash(manifest):
        raise Stage12652ReviewError("stage12651_summary_manifest_hash_drift")
    if pointer.get("contract_sha256") != stable_hash(contract) or pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12652ReviewError("stage12651_pointer_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12651_" + label)
        assert_no_leaks(record, "stage12651_" + label)
    return {"summary": summary, "manifest": manifest, "examples": examples}


def review_manifest(inputs: Mapping[str, Any]) -> dict[str, Any]:
    manifest = list(inputs["manifest"])
    examples = list(inputs["examples"])
    examples_by_id = {str(row.get("example_id")): row for row in examples}
    if len(manifest) != 280 or len(examples_by_id) != 280:
        raise Stage12652ReviewError("row_count_drift")
    if count_by(examples, "admission_family") != EXPECTED_COUNTS:
        raise Stage12652ReviewError("example_family_count_drift")
    if count_by(manifest, "training_objective") != EXPECTED_OBJECTIVES:
        raise Stage12652ReviewError("manifest_objective_count_drift")
    if count_by(manifest, "split") != EXPECTED_SPLITS:
        raise Stage12652ReviewError("manifest_split_count_drift")
    if count_by(manifest, "curriculum_lane") != EXPECTED_LANES:
        raise Stage12652ReviewError("manifest_lane_count_drift")
    source_hashes = set()
    for index, row in enumerate(manifest):
        assert_no_leaks(row, f"manifest_row:{index}")
        if row.get("record_type") != "stage12651_private_curriculum_ingest_row_v1":
            raise Stage12652ReviewError(f"manifest_record_type_drift:{index}")
        if row.get("curriculum_stage") != "stage_01_repo_and_code_knowledge":
            raise Stage12652ReviewError(f"manifest_stage_drift:{index}")
        if row.get("training_allowed") is not False or row.get("optimizer_step_authorized") is not False:
            raise Stage12652ReviewError(f"manifest_gate_drift:{index}")
        if row.get("trainer_consumable") is not True or row.get("curriculum_ingest_contract_materialized") is not True:
            raise Stage12652ReviewError(f"manifest_consumable_marker_drift:{index}")
        example = examples_by_id.get(str(row.get("source_example_id")))
        if example is None:
            raise Stage12652ReviewError(f"missing_source_example_join:{index}")
        if row.get("source_example_sha256") != stable_hash(example):
            raise Stage12652ReviewError(f"source_example_hash_drift:{index}")
        for field in ("source_row_sha256", "training_objective", "split", "loss_mask"):
            if row.get(field) != example.get(field):
                raise Stage12652ReviewError(f"source_example_binding_drift:{index}:{field}")
        lane = row.get("curriculum_lane")
        if row.get("loss_weight") != EXPECTED_WEIGHTS.get(str(lane)):
            raise Stage12652ReviewError(f"loss_weight_drift:{index}")
        source_hashes.add(str(row.get("source_row_sha256")))
    if len(source_hashes) != 280:
        raise Stage12652ReviewError("manifest_source_hash_collision")
    return {
        "curriculum_ingest_manifest_reviewed": True,
        "curriculum_ingest_manifest_review_passed": True,
        "curriculum_stage": "stage_01_repo_and_code_knowledge",
        "repo_code_curriculum_layer_complete": True,
        "trainer_consumable_rows": 280,
        "model_ready_training_rows": 280,
        "source_example_joins_verified": 280,
        "source_example_hashes_verified": 280,
        "curriculum_lane_counts": EXPECTED_LANES,
        "training_split_counts": EXPECTED_SPLITS,
        "training_objective_counts": EXPECTED_OBJECTIVES,
        "loss_weight_policy": EXPECTED_WEIGHTS,
        "stale_drift_schema_rows": 0,
        "placeholder_manifest_rows": 0,
        "raw_path_manifest_rows": 0,
        "private_lineage_manifest_rows": 0,
        "review_blocker_count": 0,
        "review_blockers": [],
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit = review_manifest(inputs)
    true_fields = {
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "repo_code_training_pack_materialized": True,
        "training_pack_materialized": True,
        "training_examples_materialized": True,
        "training_pack_reviewed": True,
        "training_pack_review_passed": True,
        "curriculum_ingestion_contract_materialized": True,
        "curriculum_ingest_manifest_reviewed": True,
        "curriculum_ingest_manifest_review_passed": True,
        "separate_training_admission_required": True,
    }
    private = {
        "record_type": "stage12652_private_repo_code_curriculum_ingest_manifest_review_packet_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "curriculum_ingest_manifest_review_audit": audit,
        "claim_boundary": {
            "curriculum_manifest": "independently_reviewed_and_passed",
            "training": "not_authorized_separate_training_authorization_required",
            "later_capability_stages": "not_materialized_by_this_stage",
        },
    }
    contract = {
        "record_type": "stage12652_public_repo_code_curriculum_ingest_manifest_review_contract_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "private_packet_sha256": stable_hash(private),
        "next_required_action": "stage12653_repo_code_training_run_authorization_preflight_only",
    }
    summary = {
        "record_type": "stage12652_public_repo_code_curriculum_ingest_manifest_review_summary_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "stage": STAGE,
        "decision": "CURRICULUM_INGEST_MANIFEST_REVIEW_PASSED_NO_TRAINING",
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12653_repo_code_training_run_authorization_preflight_only",
    }
    pointer = {
        "record_type": "stage12652_public_repo_code_curriculum_ingest_manifest_review_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "reviewed_ingest_manifest_sha256": EXPECTED_HASHES["stage12651_manifest_semantic"],
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, label)
        assert_no_leaks(record, label)
    check_false(private, "private")
    return summary, contract, private, pointer


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_curriculum_ingest_manifest_review_packet.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
