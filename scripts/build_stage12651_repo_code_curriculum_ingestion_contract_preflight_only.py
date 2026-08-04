#!/usr/bin/env python3
# Map the reviewed repo/code training pack into the maintainer curriculum without authorizing training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12651_repo_code_curriculum_ingestion_contract_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

CURRICULUM_DOC = ROOT / "docs/MAINTAINER_100M_TRAINING_STAGE_STRUCTURE.md"
S12650 = ROOT / "runs/local/artifacts/stage12650_repo_code_training_pack_independent_review_only"
S12650_SUMMARY = ROOT / "runs/summaries/stage12650_repo_code_training_pack_independent_review_only.json"
S12650_SCRIPT = ROOT / "scripts/build_stage12650_repo_code_training_pack_independent_review_only.py"
S12650_TESTS = ROOT / "tests/test_stage12650_repo_code_training_pack_independent_review_only.py"
S12649_EXAMPLES = ROOT / "runs/local/artifacts/stage12649_repo_code_training_pack_materialization_preflight_only/private/repo_code_training_examples.jsonl"

EXPECTED_HASHES = {
    "stage12650_summary": "195abbda4fe2ec006017172282366e588c64c1c54a90ccd330bff1443b61c321",
    "stage12650_contract": "02e2843e43188c30d435a9ef11da6db2ba2b37e4f16d6fb9e0869e21023f39cb",
    "stage12650_pointer": "0c21aa5cb283adf6b94ae4b9e207ce1c87a573648c97025a0ed174881d5a6e21",
    "stage12650_private_packet": "753530de381d2b2a10eb15297a01ff54345c6c5b2da084987a085014cd495bd0",
    "stage12650_script_bytes": "db35eb3ceb654ee345e59e780f7b6ecbcd4b78d8d2d1f7cafffb59713e5fdfaf",
    "stage12650_tests_bytes": "6b7c8b435e3a38e80a15d0edc1011a27e4114c27cff0a2f0a5e7f4f259291bf3",
    "stage12649_examples_bytes": "21ec4c4edd027a844042e0d04a4fa7e73611aea503302ecfa37e13dbe170261d",
    "stage12649_examples_semantic": "ab79d922b129853ad76fbdc2121296c0d75478d9f6fdcd28697587d683de62d1",
}
EXPECTED_STAGE12650_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_training_pack_independent_review_packet.json",
    "summary.json",
]
EXPECTED_COUNTS = {"repo_code_ce": 200, "source_backed_symbol_binding": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
EXPECTED_OBJECTIVES = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
CURRICULUM_STAGE = "stage_01_repo_and_code_knowledge"
CURRICULUM_STAGE_PURPOSE = "Build latent code/repository representations."
LANE_BY_OBJECTIVE = {
    "repo_code_capability_ce": {
        "curriculum_lane": "repo_code_knowledge.repo_capability_profile",
        "curriculum_signal": "repo_layout_build_docs_tests_and_maintenance_vocabulary",
        "loss_weight": 1.0,
        "replay_role": "primary_repo_code_knowledge",
    },
    "source_backed_symbol_binding_ce": {
        "curriculum_lane": "repo_code_knowledge.symbol_reference_prediction",
        "curriculum_signal": "source_backed_symbol_reference_prediction",
        "loss_weight": 0.75,
        "replay_role": "repo_code_symbol_transfer_metric",
    },
}
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
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "source_lineage",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "\x00",
    "Answer:",
    "PLACEHOLDER",
    "placeholder",
    "TODO",
    "TBD",
    "<fill",
    "source_row_id",
    "source_ref",
    "source_lineage",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
)


class Stage12651IngestionContractError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12651IngestionContractError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12651IngestionContractError(f"jsonl_object_required:{line_number}")
        rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n"
    with path.open("wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as stream:
        for row in rows:
            stream.write(json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii") + b"\n")
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
            raise Stage12651IngestionContractError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12651IngestionContractError(f"{label}_public_leak:{needle}")
    if '"model_input":' in encoded or '"target_text":' in encoded:
        raise Stage12651IngestionContractError(f"{label}_public_training_text_leak")


def assert_private_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PRIVATE_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12651IngestionContractError(f"{label}_private_leak:{needle}")


def split_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))


def component_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("admission_family")) for row in rows).items()))


def objective_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("training_objective")) for row in rows).items()))


def lane_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("curriculum_lane")) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12650).as_posix() for path in S12650.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12650_ARTIFACTS:
        raise Stage12651IngestionContractError("stage12650_artifact_manifest_drift")
    summary = read_json(S12650 / "summary.json")
    external = read_json(S12650_SUMMARY)
    contract = read_json(S12650 / "contract.json")
    pointer = read_json(S12650 / "digest_pointer.json")
    private = read_json(S12650 / "private/repo_code_training_pack_independent_review_packet.json")
    examples_bytes = S12649_EXAMPLES.read_bytes()
    examples = read_jsonl_bytes(examples_bytes)
    if summary != external:
        raise Stage12651IngestionContractError("stage12650_external_summary_mismatch")
    for label, value in (
        ("stage12650_summary", summary),
        ("stage12650_contract", contract),
        ("stage12650_pointer", pointer),
        ("stage12650_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12651IngestionContractError("pin_drift:" + label)
    for label, data in (
        ("stage12650_script_bytes", S12650_SCRIPT.read_bytes()),
        ("stage12650_tests_bytes", S12650_TESTS.read_bytes()),
        ("stage12649_examples_bytes", examples_bytes),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12651IngestionContractError("pin_drift:" + label)
    if stable_hash(examples) != EXPECTED_HASHES["stage12649_examples_semantic"]:
        raise Stage12651IngestionContractError("pin_drift:stage12649_examples_semantic")
    if pointer.get("contract_sha256") != stable_hash(contract):
        raise Stage12651IngestionContractError("stage12650_pointer_contract_hash_drift")
    if pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12651IngestionContractError("stage12650_pointer_private_hash_drift")
    if summary.get("decision") != "TRAINING_PACK_REVIEW_PASSED_SEPARATE_TRAINING_ADMISSION_REQUIRED":
        raise Stage12651IngestionContractError("stage12650_not_review_passed")
    if summary.get("training_text_renders_verified") != 280:
        raise Stage12651IngestionContractError("stage12650_missing_render_verification")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, "stage12650_" + label)
        assert_public_sanitized(record, "stage12650_" + label)
    check_false(private, "stage12650_private")
    doc = CURRICULUM_DOC.read_text(encoding="utf-8")
    if "### 1. Repo And Code Knowledge" not in doc or "symbol reference prediction" not in doc:
        raise Stage12651IngestionContractError("curriculum_doc_missing_repo_code_stage")
    return {"summary": summary, "examples": examples}


def build_ingest_manifest(inputs: Mapping[str, Any]) -> list[dict[str, Any]]:
    examples = list(inputs["examples"])
    if len(examples) != 280 or component_counts(examples) != EXPECTED_COUNTS:
        raise Stage12651IngestionContractError("example_count_or_family_drift")
    if split_counts(examples) != EXPECTED_SPLITS or objective_counts(examples) != EXPECTED_OBJECTIVES:
        raise Stage12651IngestionContractError("example_split_or_objective_drift")
    manifest: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in examples:
        objective = str(row.get("training_objective"))
        lane = LANE_BY_OBJECTIVE.get(objective)
        if lane is None:
            raise Stage12651IngestionContractError("unknown_training_objective:" + objective)
        if row.get("training_allowed") is not False or row.get("optimizer_ready") is not True:
            raise Stage12651IngestionContractError("example_gate_or_optimizer_marker_drift")
        if row.get("example_id") in seen_ids:
            raise Stage12651IngestionContractError("duplicate_example_id")
        seen_ids.add(str(row.get("example_id")))
        assert_private_sanitized(row, "stage12649_example")
        manifest.append({
            "record_type": "stage12651_private_curriculum_ingest_row_v1",
            "ingest_row_id": str(row["example_id"]).replace("stage12649_training_", "stage12651_ingest_"),
            "source_example_id": row["example_id"],
            "source_row_sha256": row["source_row_sha256"],
            "source_example_sha256": stable_hash(row),
            "curriculum_stage": CURRICULUM_STAGE,
            "curriculum_stage_purpose": CURRICULUM_STAGE_PURPOSE,
            "curriculum_lane": lane["curriculum_lane"],
            "curriculum_signal": lane["curriculum_signal"],
            "replay_role": lane["replay_role"],
            "admission_family": row["admission_family"],
            "training_objective": objective,
            "split": row["split"],
            "loss_mask": row["loss_mask"],
            "loss_weight": lane["loss_weight"],
            "sequence_role": "supervised_target_only",
            "trainer_consumable": True,
            "curriculum_ingest_contract_materialized": True,
            "training_allowed": False,
            "optimizer_step_authorized": False,
        })
    if len(manifest) != 280:
        raise Stage12651IngestionContractError("ingest_manifest_count_drift")
    return manifest


def audit_manifest(manifest: list[dict[str, Any]]) -> dict[str, Any]:
    if len(manifest) != 280:
        raise Stage12651IngestionContractError("manifest_count_drift")
    if split_counts(manifest) != EXPECTED_SPLITS:
        raise Stage12651IngestionContractError("manifest_split_drift")
    if objective_counts(manifest) != EXPECTED_OBJECTIVES:
        raise Stage12651IngestionContractError("manifest_objective_drift")
    if len({row["source_row_sha256"] for row in manifest}) != 280:
        raise Stage12651IngestionContractError("manifest_source_hash_collision")
    if any(row.get("training_allowed") is not False or row.get("optimizer_step_authorized") is not False for row in manifest):
        raise Stage12651IngestionContractError("manifest_training_gate_drift")
    for row in manifest:
        assert_private_sanitized(row, "ingest_manifest_row")
    return {
        "curriculum_ingestion_contract_materialized": True,
        "curriculum_stage": CURRICULUM_STAGE,
        "repo_code_curriculum_layer_complete": True,
        "trainer_consumable_rows": 280,
        "model_ready_training_rows": 280,
        "repo_code_ce_ingest_rows": 200,
        "symbol_binding_ingest_rows": 80,
        "training_split_counts": EXPECTED_SPLITS,
        "training_objective_counts": EXPECTED_OBJECTIVES,
        "curriculum_lane_counts": lane_counts(manifest),
        "loss_weight_policy": {
            "repo_code_knowledge.repo_capability_profile": 1.0,
            "repo_code_knowledge.symbol_reference_prediction": 0.75,
        },
        "source_example_hashes_verified": 280,
        "unique_source_row_hashes": 280,
        "placeholder_ingest_rows": 0,
        "raw_path_ingest_rows": 0,
        "private_lineage_ingest_rows": 0,
        "excluded_later_stage_lanes": [
            "structured_repo_state",
            "maintainer_action_policy",
            "long_horizon_state_transitions",
            "edit_localization",
            "bounded_decoder",
            "verifier_conditioned_repair",
        ],
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    manifest = build_ingest_manifest(inputs)
    audit = audit_manifest(manifest)
    manifest_hash = stable_hash(manifest)
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
        "separate_training_admission_required": True,
    }
    private = {
        "record_type": "stage12651_private_repo_code_curriculum_ingestion_contract_packet_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "curriculum_doc_sha256": sha256_bytes(CURRICULUM_DOC.read_bytes()),
        "ingest_manifest_sha256": manifest_hash,
        "curriculum_ingestion_audit": audit,
        "claim_boundary": {
            "curriculum": "repo_code_knowledge_ingestion_contract_materialized",
            "training": "not_authorized_separate_training_run_authorization_required",
            "later_capability_stages": "not_materialized_by_this_stage",
        },
    }
    contract = {
        "record_type": "stage12651_public_repo_code_curriculum_ingestion_contract_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "ingest_manifest_sha256": manifest_hash,
        "private_packet_sha256": stable_hash(private),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only",
    }
    summary = {
        "record_type": "stage12651_public_repo_code_curriculum_ingestion_contract_summary_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "stage": STAGE,
        "decision": "CURRICULUM_INGESTION_CONTRACT_MATERIALIZED_NO_TRAINING",
        "ingest_manifest_sha256": manifest_hash,
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
        "next_required_action": "stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only",
    }
    pointer = {
        "record_type": "stage12651_public_repo_code_curriculum_ingestion_contract_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "ingest_manifest_sha256": manifest_hash,
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        check_false(record, label)
        assert_public_sanitized(record, label)
    check_false(private, "private")
    return summary, contract, private, pointer, manifest


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer, manifest = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_curriculum_ingestion_contract_packet.json", private)
    write_jsonl(out / "private/repo_code_curriculum_ingest_manifest.jsonl", manifest)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
