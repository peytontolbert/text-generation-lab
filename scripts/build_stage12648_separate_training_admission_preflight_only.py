#!/usr/bin/env python3
# Decide whether the completed repo/code knowledge layer is ready for training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12648_separate_training_admission_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12647 = ROOT / "runs/local/artifacts/stage12647_repo_code_knowledge_completion_admission_preflight_only"
S12647_SUMMARY = ROOT / "runs/summaries/stage12647_repo_code_knowledge_completion_admission_preflight_only.json"
S12647_SCRIPT = ROOT / "scripts/build_stage12647_repo_code_knowledge_completion_admission_preflight_only.py"
S12647_TESTS = ROOT / "tests/test_stage12647_repo_code_knowledge_completion_admission_preflight_only.py"

EXPECTED_HASHES = {
    "stage12647_summary": "645f5f71dc92f0ae1a1e3d658ce48329220a6544114ebea3965916f578c02657",
    "stage12647_contract": "66e8a8bbd2c6b13654bcf9dc8f26e1429bfef78b3e80eac4b34e397f2ca0c413",
    "stage12647_pointer": "626b0fe2cb98a92bb9e7a53343fd294e8b69faff37c04512fc45f274576a797f",
    "stage12647_private_packet": "3aa776c05326be86febca187203f8a3c33a499ce0c81412a8037b400d28cd31d",
    "stage12647_admitted_rows_bytes": "7872bcff8627577be0a8270bdda1760ecae8a2c1f197d0a6a0317958277e3d65",
    "stage12647_script_bytes": "be9b5fc900a7bb14f088c7c5528e1a062550c5e168f03a2220b3b92a8693ab08",
    "stage12647_tests_bytes": "c4df521ee4fbc1f8a1f1e7011ccdb82f08d691fa620f4b68f92a55275b374efe",
}
EXPECTED_STAGE12647_ARTIFACTS = [
    "contract.json",
    "digest_pointer.json",
    "private/admitted_repo_code_knowledge_rows.jsonl",
    "private/repo_code_knowledge_completion_admission_packet.json",
    "summary.json",
]
EXPECTED_ADMITTED_COUNTS = {"repo_code_ce": 200, "source_backed_symbol_binding": 80}
EXPECTED_SPLITS = {"eval": 64, "strict_eval": 63, "train": 153}
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
    "training_pack_materialized",
    "training_examples_materialized",
    "optimizer_step_authorized",
)
PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/",
    "/arxiv/",
    "jsonl",
    "row_id",
    "source_row_id",
    "source_ref",
    "old_source_ref_path",
    "raw_stream",
    "stdout.raw",
    "stderr.raw",
    "repository_root",
    "patch_path",
    "production_path",
)


class Stage12648TrainingAdmissionError(RuntimeError):
    pass


def stable_hash(value: Any) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12648TrainingAdmissionError("json_object_required:" + path.name)
    return value


def read_jsonl_bytes(data: bytes) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(data.decode("utf-8").splitlines(), start=1):
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise Stage12648TrainingAdmissionError(f"jsonl_object_required:{line_number}")
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


def no_training_fields() -> dict[str, Any]:
    return {field: False for field in FALSE_FIELDS}


def check_false(record: Mapping[str, Any], label: str) -> None:
    for field in FALSE_FIELDS:
        if record.get(field) is not False:
            raise Stage12648TrainingAdmissionError(f"{label}_gate_drift:{field}")


def assert_public_sanitized(record: Mapping[str, Any], label: str) -> None:
    encoded = json.dumps(record, sort_keys=True, ensure_ascii=True)
    for needle in PUBLIC_FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12648TrainingAdmissionError(f"{label}_public_leak:{needle}")


def split_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))


def component_counts(rows: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get("admission_family")) for row in rows).items()))


def load_stage12647() -> dict[str, Any]:
    emitted = sorted(path.relative_to(S12647).as_posix() for path in S12647.rglob("*") if path.is_file())
    if emitted != EXPECTED_STAGE12647_ARTIFACTS:
        raise Stage12648TrainingAdmissionError("stage12647_artifact_manifest_drift")
    summary = read_json(S12647 / "summary.json")
    external = read_json(S12647_SUMMARY)
    contract = read_json(S12647 / "contract.json")
    pointer = read_json(S12647 / "digest_pointer.json")
    private = read_json(S12647 / "private/repo_code_knowledge_completion_admission_packet.json")
    admitted_bytes = (S12647 / "private/admitted_repo_code_knowledge_rows.jsonl").read_bytes()
    if summary != external:
        raise Stage12648TrainingAdmissionError("stage12647_external_summary_mismatch")
    for label, value in (
        ("stage12647_summary", summary),
        ("stage12647_contract", contract),
        ("stage12647_pointer", pointer),
        ("stage12647_private_packet", private),
    ):
        if stable_hash(value) != EXPECTED_HASHES[label]:
            raise Stage12648TrainingAdmissionError("pin_drift:" + label)
    for label, data in (
        ("stage12647_admitted_rows_bytes", admitted_bytes),
        ("stage12647_script_bytes", S12647_SCRIPT.read_bytes()),
        ("stage12647_tests_bytes", S12647_TESTS.read_bytes()),
    ):
        if sha256_bytes(data) != EXPECTED_HASHES[label]:
            raise Stage12648TrainingAdmissionError("pin_drift:" + label)
    admitted = read_jsonl_bytes(admitted_bytes)
    if pointer.get("contract_sha256") != stable_hash(contract):
        raise Stage12648TrainingAdmissionError("stage12647_pointer_contract_hash_drift")
    if pointer.get("private_packet_sha256") != stable_hash(private):
        raise Stage12648TrainingAdmissionError("stage12647_pointer_private_hash_drift")
    if pointer.get("admitted_manifest_sha256") != stable_hash(admitted):
        raise Stage12648TrainingAdmissionError("stage12647_pointer_admitted_hash_drift")
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer)):
        assert_public_sanitized(record, "stage12647_" + label)
    return {"summary": summary, "contract": contract, "pointer": pointer, "private": private, "admitted": admitted}


def audit_training_admission(stage12647: Mapping[str, Any]) -> dict[str, Any]:
    summary = stage12647["summary"]
    admitted = stage12647["admitted"]
    if summary.get("repo_code_knowledge_stage_complete") is not True:
        raise Stage12648TrainingAdmissionError("repo_code_stage_not_complete")
    if summary.get("dataset_rows_admitted") is not True or summary.get("repo_code_rows_admitted") is not True:
        raise Stage12648TrainingAdmissionError("repo_code_rows_not_admitted")
    if summary.get("repo_code_knowledge_rows_admitted") != 280:
        raise Stage12648TrainingAdmissionError("repo_code_admitted_count_drift")
    if summary.get("model_ready_training_rows") != 0:
        raise Stage12648TrainingAdmissionError("unexpected_model_ready_rows")
    if len(admitted) != 280 or component_counts(admitted) != EXPECTED_ADMITTED_COUNTS:
        raise Stage12648TrainingAdmissionError("admitted_manifest_count_drift")
    if split_counts(admitted) != EXPECTED_SPLITS:
        raise Stage12648TrainingAdmissionError("admitted_manifest_split_drift")
    if len({row.get("source_row_sha256") for row in admitted}) != 280:
        raise Stage12648TrainingAdmissionError("admitted_source_hash_collision")
    for row in admitted:
        if row.get("repo_code_knowledge_admitted") is not True:
            raise Stage12648TrainingAdmissionError("admitted_row_marker_drift")
        if row.get("training_allowed") is not False:
            raise Stage12648TrainingAdmissionError("admitted_row_training_gate_drift")
        encoded = json.dumps(row, sort_keys=True)
        if "/arxiv/" in encoded or "/data/" in encoded or "source_row_id" in encoded:
            raise Stage12648TrainingAdmissionError("admitted_row_not_hash_only")
    blockers = [
        "model_ready_training_rows_zero",
        "admitted_curriculum_ledger_is_hash_only_not_trainable_text",
        "repo_code_training_pack_not_materialized",
        "training_pack_independent_review_missing",
        "retention_eval_and_shortcut_baseline_plan_not_materialized",
        "explicit_training_authorization_missing",
    ]
    return {
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "repo_code_knowledge_rows_admitted": 280,
        "admitted_component_counts": EXPECTED_ADMITTED_COUNTS,
        "admitted_split_counts": EXPECTED_SPLITS,
        "hash_only_admitted_rows": 280,
        "model_ready_training_rows": 0,
        "training_admission_decision": "BLOCKED_TRAINING_PACK_MATERIALIZATION_REQUIRED",
        "training_blocker_count": len(blockers),
        "training_blockers": blockers,
    }


def build_packet(stage12647: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    audit = audit_training_admission(stage12647)
    true_fields = {
        "stage12648_separate_training_admission_preflight_performed": True,
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "separate_training_admission_required": True,
    }
    private = {
        "record_type": "stage12648_private_separate_training_admission_preflight_only_v1",
        **no_training_fields(),
        **true_fields,
        "reviewed_input_hashes": EXPECTED_HASHES,
        "training_admission_audit": audit,
        "decision": audit["training_admission_decision"],
    }
    contract = {
        "record_type": "stage12648_public_separate_training_admission_preflight_contract_v1",
        **no_training_fields(),
        **true_fields,
        "training_admission_audit_sha256": stable_hash(audit),
        "private_packet_sha256": stable_hash(private),
        **audit,
        "claim_boundary": {
            "repo_code_knowledge": "complete_and_dataset_rows_admitted",
            "training": "blocked_until_trainable_pack_materialized_reviewed_and_authorized",
            "gpu": "not_requested",
            "vm": "not_used",
            "next": "materialize_repo_code_training_pack_preflight",
        },
    }
    summary = {
        "record_type": "stage12648_public_separate_training_admission_preflight_summary_v1",
        **no_training_fields(),
        **true_fields,
        "stage": STAGE,
        "decision": audit["training_admission_decision"],
        "training_admission_audit_sha256": stable_hash(audit),
        "private_packet_sha256": stable_hash(private),
        **audit,
        "next_required_action": "stage12649_repo_code_training_pack_materialization_preflight_only",
    }
    for label, record in (("summary", summary), ("contract", contract)):
        check_false(record, "stage12648_" + label)
        assert_public_sanitized(record, "stage12648_" + label)
    check_false(private, "stage12648_private")
    return summary, contract, private


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, contract, private = build_packet(load_stage12647())
    pointer = {
        "record_type": "stage12648_public_separate_training_admission_preflight_pointer_v1",
        **no_training_fields(),
        "stage12648_separate_training_admission_preflight_performed": True,
        "repo_code_knowledge_stage_complete": True,
        "dataset_rows_admitted": True,
        "repo_code_rows_admitted": True,
        "separate_training_admission_required": True,
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "training_admission_audit_sha256": stable_hash(private["training_admission_audit"]),
    }
    check_false(pointer, "stage12648_pointer")
    assert_public_sanitized(pointer, "stage12648_pointer")
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/separate_training_admission_preflight_only.json", private)
    write_json(out / "summary.json", summary)
    write_json(summary_path, summary)
    fsync_dir(out / "private")
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
