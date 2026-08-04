#!/usr/bin/env python3
# Preflight the reviewed repo/code curriculum ingest for a future training run, without authorizing execution.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12653_repo_code_training_run_authorization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

CURRICULUM_DOC = ROOT / "docs/MAINTAINER_100M_TRAINING_STAGE_STRUCTURE.md"
S12652 = ROOT / "runs/local/artifacts/stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only"
S12652_SUMMARY = ROOT / "runs/summaries/stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only.json"
S12652_SCRIPT = ROOT / "scripts/build_stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only.py"
S12652_TESTS = ROOT / "tests/test_stage12652_repo_code_curriculum_ingest_manifest_materialization_review_only.py"
S12651_MANIFEST = ROOT / "runs/local/artifacts/stage12651_repo_code_curriculum_ingestion_contract_preflight_only/private/repo_code_curriculum_ingest_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12652_summary": "340cae89aca2ead2c963a59d2a32024552b91b7bffa6221d763434a413cddb56",
    "stage12652_contract": "bfe4033669d75e4f2a222621899de3c06a1d81468d6904060263b24b1d60ebc4",
    "stage12652_pointer": "4fc6b3874a9b8591391f356d9ba4551b703f24d8979bb25c337dffca5f6d352d",
    "stage12652_private_packet": "d6b6ec52f4e79f50994f580e02a6aaef54f78ca388afdeddc2b90082546791cc",
    "stage12652_script_bytes": "d35df89961850e3848ac6de67732965b5dcad58c78372e1c714903728b0250a1",
    "stage12652_tests_bytes": "c152e69e4910ec6d7f6f75a22451c6d1b7364cf8de779824abc68aecb00a8cc4",
    "stage12651_manifest_bytes": "d19e8b0139d1dd179ca369b7db8c4252b8ac4e711855208fd273ec9419a46cb1",
    "stage12651_manifest_semantic": "21b3d427575a7883950600ab93e0980d3f74ad52f146bde58d6eba27144ead79",
    "curriculum_doc_bytes": "cf6204f501f5226c96d9fe892334ac19822f6473b98d4cbcf2dfcb05fd0551af",
}
EXPECTED_STAGE12652_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/repo_code_curriculum_ingest_manifest_review_packet.json",
    "summary.json",
]
EXPECTED_LANES = {
    "repo_code_knowledge.repo_capability_profile": 200,
    "repo_code_knowledge.symbol_reference_prediction": 80,
}
EXPECTED_OBJECTIVES = {"repo_code_capability_ce": 200, "source_backed_symbol_binding_ce": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
EXPECTED_WEIGHTS = {
    "repo_code_knowledge.repo_capability_profile": 1.0,
    "repo_code_knowledge.symbol_reference_prediction": 0.75,
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
FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "model_input",
    "target_text",
    "source_lineage",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repo_graph_and_symbol_binding",
    "TODO",
    "TBD",
    "<fill",
)
BLOCKERS = [
    "explicit_training_authorization_missing",
    "retention_eval_and_shortcut_baseline_plan_not_materialized",
    "optimizer_context_not_bound_to_trainer_implementation",
    "checkpoint_parent_not_selected",
    "cuda2_only_runtime_contract_not_materialized",
    "training_pack_authorization_review_missing",
]


class Stage12653TrainingRunAuthorizationError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12653TrainingRunAuthorizationError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12653TrainingRunAuthorizationError(f"jsonl_object_required:{line_number}")
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
            raise Stage12653TrainingRunAuthorizationError(f"{label}_gate_drift:{field}")


def assert_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12653TrainingRunAuthorizationError(f"{label}_leak_or_drift:{needle}")


def count_by(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(field)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12652).as_posix() for path in S12652.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12652_ARTIFACTS:
        raise Stage12653TrainingRunAuthorizationError("stage12652_artifact_manifest_drift")
    summary = read_json(S12652 / "summary.json")
    external = read_json(S12652_SUMMARY)
    contract = read_json(S12652 / "contract.json")
    pointer = read_json(S12652 / "digest_pointer.json")
    private = read_json(S12652 / "private/repo_code_curriculum_ingest_manifest_review_packet.json")
    manifest_bytes = S12651_MANIFEST.read_bytes()
    manifest = read_jsonl_bytes(manifest_bytes)
    if summary != external:
        raise Stage12653TrainingRunAuthorizationError("stage12652_external_summary_mismatch")
    for label, value in (
        ("stage12652_summary", summary),
        ("stage12652_contract", contract),
        ("stage12652_pointer", pointer),
        ("stage12652_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12653TrainingRunAuthorizationError("pin_drift:" + label)
    for label, data in (
        ("stage12652_script_bytes", S12652_SCRIPT.read_bytes()),
        ("stage12652_tests_bytes", S12652_TESTS.read_bytes()),
        ("stage12651_manifest_bytes", manifest_bytes),
        ("curriculum_doc_bytes", CURRICULUM_DOC.read_bytes()),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12653TrainingRunAuthorizationError("pin_drift:" + label)
    if stable_hash(manifest) != EXPECTED_HASHES["stage12651_manifest_semantic"]:
        raise Stage12653TrainingRunAuthorizationError("pin_drift:stage12651_manifest_semantic")
    if pointer.get("contract_sha256") != stable_hash(contract) or pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12653TrainingRunAuthorizationError("stage12652_pointer_hash_drift")
    if summary.get("decision") != "CURRICULUM_INGEST_MANIFEST_REVIEW_PASSED_NO_TRAINING":
        raise Stage12653TrainingRunAuthorizationError("stage12652_not_review_passed")
    if summary.get("next_required_action") != STAGE:
        raise Stage12653TrainingRunAuthorizationError("stage12652_next_action_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, "stage12652_" + label)
        assert_sanitized(record, "stage12652_" + label)
    return {"summary": summary, "manifest": manifest}


def audit_curriculum_readiness(inputs: Mapping[str, Any]) -> dict[str, Any]:
    summary = inputs["summary"]
    manifest = list(inputs["manifest"])
    if len(manifest) != 280:
        raise Stage12653TrainingRunAuthorizationError("manifest_count_drift")
    if summary.get("curriculum_ingest_manifest_review_passed") is not True:
        raise Stage12653TrainingRunAuthorizationError("ingest_review_not_passed")
    if summary.get("trainer_consumable_rows") != 280 or summary.get("model_ready_training_rows") != 280:
        raise Stage12653TrainingRunAuthorizationError("trainer_consumable_count_drift")
    if count_by(manifest, "curriculum_lane") != EXPECTED_LANES:
        raise Stage12653TrainingRunAuthorizationError("lane_count_drift")
    if count_by(manifest, "training_objective") != EXPECTED_OBJECTIVES:
        raise Stage12653TrainingRunAuthorizationError("objective_count_drift")
    if count_by(manifest, "split") != EXPECTED_SPLITS:
        raise Stage12653TrainingRunAuthorizationError("split_count_drift")
    for index, row in enumerate(manifest):
        assert_sanitized(row, f"manifest_row:{index}")
        if row.get("trainer_consumable") is not True:
            raise Stage12653TrainingRunAuthorizationError(f"trainer_consumable_marker_drift:{index}")
        if row.get("training_allowed") is not False or row.get("optimizer_step_authorized") is not False:
            raise Stage12653TrainingRunAuthorizationError(f"manifest_gate_drift:{index}")
        lane = str(row.get("curriculum_lane"))
        if row.get("loss_weight") != EXPECTED_WEIGHTS.get(lane):
            raise Stage12653TrainingRunAuthorizationError(f"loss_weight_drift:{index}")
    train_rows = [row for row in manifest if row.get("split") == "train"]
    eval_rows = [row for row in manifest if row.get("split") == "eval"]
    strict_rows = [row for row in manifest if row.get("split") == "strict_eval"]
    if not train_rows or not eval_rows or not strict_rows:
        raise Stage12653TrainingRunAuthorizationError("split_role_missing")
    return {
        "repo_code_curriculum_layer_complete": True,
        "curriculum_ingest_manifest_review_passed": True,
        "curriculum_stage": "stage_01_repo_and_code_knowledge",
        "trainer_consumable_rows": 280,
        "model_ready_training_rows": 280,
        "train_rows_available": len(train_rows),
        "eval_rows_reserved": len(eval_rows),
        "strict_eval_rows_reserved_not_admitted": len(strict_rows),
        "training_split_counts": EXPECTED_SPLITS,
        "training_objective_counts": EXPECTED_OBJECTIVES,
        "curriculum_lane_counts": EXPECTED_LANES,
        "loss_weight_policy": EXPECTED_WEIGHTS,
        "train_eval_split_policy": {
            "train": "eligible_for_future_optimizer_input_after_explicit_authorization",
            "eval": "reserved_for_nonsealed_retention_measurement_only",
            "strict_eval": "reserved_and_not_admitted_until_separate_strict_eval_stage",
        },
        "optimizer_run_contract": {
            "run_kind": "repo_code_stage_01_supervised_ce",
            "trainable_stage": "stage_01_repo_and_code_knowledge",
            "data_manifest": "stage12651_repo_code_curriculum_ingest_manifest",
            "objectives": EXPECTED_OBJECTIVES,
            "loss_weights": EXPECTED_WEIGHTS,
            "parent_checkpoint": None,
            "trainer_implementation": None,
            "optimizer_and_context": None,
            "max_train_rows": 153,
            "eval_rows": 64,
            "strict_eval_rows_excluded": 63,
            "cuda_visible_devices_required": "2",
            "forbidden_gpu_ids": ["0", "1"],
        },
        "authorization_blocker_count": len(BLOCKERS),
        "authorization_blockers": BLOCKERS,
    }


def build_packet(inputs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit = audit_curriculum_readiness(inputs)
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
        "stage12653_training_run_authorization_preflight_performed": True,
    }
    private = {
        "record_type": "stage12653_private_repo_code_training_run_authorization_preflight_v1",
        **false_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "training_run_authorization_audit": audit,
        "claim_boundary": {
            "curriculum_ingest": "reviewed_and_trainer_consumable",
            "run_contract": "drafted_but_not_authorized",
            "training": "blocked_until_explicit_authorization_and_runtime_contract",
        },
    }
    contract = {
        "record_type": "stage12653_public_repo_code_training_run_authorization_preflight_contract_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "private_packet_sha256": stable_hash(private),
        "next_required_action": "stage12654_repo_code_training_authorization_independent_review_only",
    }
    summary = {
        "record_type": "stage12653_public_repo_code_training_run_authorization_preflight_summary_v1",
        **false_fields(),
        **true_fields,
        **audit,
        "stage": STAGE,
        "decision": "BLOCKED_EXPLICIT_TRAINING_AUTHORIZATION_AND_RUNTIME_CONTRACT_REQUIRED",
        "private_packet_sha256": stable_hash(private),
        "contract_sha256": stable_hash(contract),
        "next_required_action": "stage12654_repo_code_training_authorization_independent_review_only",
    }
    pointer = {
        "record_type": "stage12653_public_repo_code_training_run_authorization_preflight_pointer_v1",
        **false_fields(),
        **true_fields,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "reviewed_stage12652_summary_sha256": EXPECTED_HASHES["stage12652_summary"],
        "reviewed_stage12651_manifest_sha256": EXPECTED_HASHES["stage12651_manifest_semantic"],
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("private", private)):
        check_false(record, label)
        assert_sanitized(record, label)
    return summary, contract, private, pointer


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private, pointer = build_packet(load_inputs())
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_training_run_authorization_preflight.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
