#!/usr/bin/env python3
# Build the Structured Repo State training-admission preflight pack without launching training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12662_structured_repo_state_training_admission_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12661_SUMMARY = ROOT / "runs/summaries/stage12661_structured_repo_state_training_eligibility_independent_review_only.json"
S12661_MATRIX = ROOT / "runs/local/artifacts/stage12661_structured_repo_state_training_eligibility_independent_review_only/admission_matrix.json"
S12661_ADMITTED = ROOT / "runs/local/artifacts/stage12661_structured_repo_state_training_eligibility_independent_review_only/private/admitted_structured_repo_state_rows.jsonl"
S12656_MANIFEST = ROOT / "runs/local/artifacts/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only/private/shortcut_resilient_repo_code_curriculum_ingest_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12661_summary": "65a583727483ef87f8e5f9e0deddca99b75f8ead5046819d7a9a41303919ea5f",
    "stage12661_matrix": "943008c4a65d2da353de6b7d8ae27c9e0c20988cabb8bcda64b9fc72b555c58d",
    "stage12661_admitted": "479075196740d1bdd26cc2cb59ee1c726f140c814513517072d5b5514e154a9a",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12663_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)
UPSTREAM_FALSE_FIELDS = (
    "implementation_ready", "stage12662_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER",
    "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder",
    "TODO", "TBD", "input_text", "target_text", "query_text", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {"eval": 315, "strict_eval": 315, "train": 1557}
EXPECTED_OBJECTIVES = {
    "structured_repo_state.evidence_role": 729,
    "structured_repo_state.evidence_route": 729,
    "structured_repo_state.hypothesis_status": 729,
}


class Stage12662AdmissionPreflightError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12662AdmissionPreflightError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12662AdmissionPreflightError(f"jsonl_object_required:{path.name}:{line_number}")
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
            stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True).encode("ascii") + b"\n")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12662AdmissionPreflightError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12662AdmissionPreflightError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12661_summary", S12661_SUMMARY),
        ("stage12661_matrix", S12661_MATRIX),
        ("stage12661_admitted", S12661_ADMITTED),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12662AdmissionPreflightError("pin_drift:" + label)
    summary = read_json(S12661_SUMMARY)
    matrix = read_json(S12661_MATRIX)
    admitted = read_jsonl(S12661_ADMITTED)
    check_false(summary, "stage12661_summary", UPSTREAM_FALSE_FIELDS)
    check_false(matrix, "stage12661_matrix", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12662AdmissionPreflightError("stage12661_next_action_drift")
    if summary.get("dataset_rows_admitted") is not True or summary.get("structured_repo_state_rows_admitted") is not True:
        raise Stage12662AdmissionPreflightError("stage12661_rows_not_admitted")
    return {"summary": summary, "matrix": matrix, "admitted": admitted}


def repo_code_sidecar_status() -> dict[str, Any]:
    if not S12656_MANIFEST.exists():
        return {"repo_code_sidecar_present": False, "repo_code_trainer_consumable_rows": 0}
    rows = read_jsonl(S12656_MANIFEST)
    return {
        "repo_code_sidecar_present": True,
        "repo_code_trainer_consumable_rows": sum(1 for row in rows if row.get("trainer_consumable") is True),
        "repo_code_manifest_rows": len(rows),
        "repo_code_contract_merge_required": True,
    }


def validate_admitted_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "admitted_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2187:
        raise Stage12662AdmissionPreflightError("admitted_count_drift")
    split_counts = dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))
    objective_counts = dict(sorted(collections.Counter(str(row.get("training_objective")) for row in rows).items()))
    label_counts = dict(sorted(collections.Counter(str(row.get("target_label")) for row in rows).items()))
    if split_counts != EXPECTED_SPLITS:
        raise Stage12662AdmissionPreflightError("split_count_drift")
    if objective_counts != EXPECTED_OBJECTIVES:
        raise Stage12662AdmissionPreflightError("objective_count_drift")
    for row in rows:
        if row.get("trainer_consumable") is not True or row.get("row_admitted") is not True:
            raise Stage12662AdmissionPreflightError("row_not_trainer_consumable")
        if row.get("loss_weight") != 1.0:
            raise Stage12662AdmissionPreflightError("loss_weight_drift")
        if row.get("loss_mask") != {"decoder_ce": 0.0, "structured_repo_state_ce": 1.0}:
            raise Stage12662AdmissionPreflightError("loss_mask_drift")
        if row.get("curriculum_layer") != "structured_repo_state":
            raise Stage12662AdmissionPreflightError("curriculum_layer_drift")
        if "root_candidate_id" in row or "training_candidate_id" in row:
            raise Stage12662AdmissionPreflightError("stable_candidate_id_leak")
    return {"split_counts": split_counts, "objective_counts": objective_counts, "target_label_counts": label_counts}


def trainer_manifest_row(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    out = {
        "manifest_row_id": f"srs_admitted_{index:06d}",
        "split": row["split"],
        "curriculum_layer": row["curriculum_layer"],
        "training_objective": row["training_objective"],
        "input_state": row["input_state"],
        "target_label": row["target_label"],
        "loss_mask": row["loss_mask"],
        "loss_weight": row["loss_weight"],
        "trainer_consumable": True,
        "row_admitted": True,
        "source_admission_stage": "stage12661_structured_repo_state_training_eligibility_independent_review_only",
    }
    assert_no_forbidden(out, "trainer_manifest_row", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return out


def build_trainer_manifest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trainer_rows = [trainer_manifest_row(row, index) for index, row in enumerate(rows, start=1)]
    signatures: dict[str, set[str]] = collections.defaultdict(set)
    for row in trainer_rows:
        signature = stable_hash({
            "input_state": row["input_state"],
            "target_label": row["target_label"],
            "training_objective": row["training_objective"],
        })
        signatures[signature].add(str(row["split"]))
    cross_split_signatures = {signature for signature, splits in signatures.items() if len(splits) > 1}
    for row in trainer_rows:
        signature = stable_hash({
            "input_state": row["input_state"],
            "target_label": row["target_label"],
            "training_objective": row["training_objective"],
        })
        row["compact_signature_cross_split_duplicate"] = signature in cross_split_signatures
        if signature in cross_split_signatures:
            row["loss_weight"] = 0.25
    return trainer_rows


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    validation = validate_admitted_rows(loaded["admitted"])
    trainer_rows = build_trainer_manifest(loaded["admitted"])
    duplicate_rows = sum(1 for row in trainer_rows if row["compact_signature_cross_split_duplicate"])
    duplicate_groups = len({
        stable_hash({"input_state": row["input_state"], "target_label": row["target_label"], "training_objective": row["training_objective"]})
        for row in trainer_rows
        if row["compact_signature_cross_split_duplicate"]
    })
    sidecar = repo_code_sidecar_status()
    matrix = {
        "record_type": "stage12662_structured_repo_state_training_admission_matrix_v1",
        "stage": STAGE,
        "structured_repo_state_training_pack_ready": True,
        "structured_repo_state_trainer_rows": len(trainer_rows),
        "trainer_manifest_rows": len(trainer_rows),
        "cross_split_duplicate_compact_signature_groups": duplicate_groups,
        "cross_split_duplicate_compact_signature_rows": duplicate_rows,
        "cross_split_duplicate_loss_weight": 0.25,
        "split_counts": validation["split_counts"],
        "objective_counts": validation["objective_counts"],
        "target_label_counts": validation["target_label_counts"],
        "repo_code_sidecar_status": sidecar,
        "next_required_action": "stage12663_structured_repo_state_training_admission_independent_review_only",
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_preflight_passed": True,
        **false_fields(),
    }
    summary = {
        "record_type": "stage12662_public_structured_repo_state_training_admission_preflight_summary_v1",
        "stage": STAGE,
        "decision": "STRUCTURED_REPO_STATE_TRAINING_ADMISSION_PREFLIGHT_PASSED_NO_TRAINING_RUN",
        "structured_repo_state_training_pack_ready": True,
        "structured_repo_state_trainer_rows": len(trainer_rows),
        "trainer_manifest_rows": len(trainer_rows),
        "cross_split_duplicate_compact_signature_groups": duplicate_groups,
        "cross_split_duplicate_compact_signature_rows": duplicate_rows,
        "cross_split_duplicate_loss_weight": 0.25,
        "split_counts": validation["split_counts"],
        "objective_counts": validation["objective_counts"],
        "repo_code_trainer_consumable_rows_available_for_later_pack_merge": sidecar["repo_code_trainer_consumable_rows"],
        "next_required_action": "stage12663_structured_repo_state_training_admission_independent_review_only",
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_preflight_passed": True,
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, matrix, trainer_rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, matrix, trainer_rows = build_packet()
    private = {
        "record_type": "stage12662_private_structured_repo_state_training_admission_packet_v1",
        "stage": STAGE,
        "stage12661_admitted_rows_sha256": EXPECTED_HASHES["stage12661_admitted"],
        "trainer_manifest_sha256": stable_hash(trainer_rows),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12662_structured_repo_state_training_admission_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12661_structured_repo_state_training_eligibility_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "trainer_manifest_sha256": stable_hash(trainer_rows),
        "private_packet_sha256": stable_hash(private),
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_preflight_passed": True,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12662_structured_repo_state_training_admission_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "matrix_sha256": stable_hash(matrix),
        "trainer_manifest_sha256": stable_hash(trainer_rows),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "training_admission_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/structured_repo_state_training_admission_packet.json", private)
    write_jsonl(out / "private/structured_repo_state_trainer_manifest.jsonl", trainer_rows)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
