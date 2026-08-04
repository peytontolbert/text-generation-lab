#!/usr/bin/env python3
# Independently review and admit Structured Repo State rows for trainer consumption, without authorizing training execution.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12661_structured_repo_state_training_eligibility_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12660_SUMMARY = ROOT / "runs/summaries/stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only.json"
S12660_MATRIX = ROOT / "runs/local/artifacts/stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only/training_eligible_candidate_matrix.json"
S12660_CANDIDATES = ROOT / "runs/local/artifacts/stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only/private/training_eligible_structured_repo_state_candidates.jsonl"

EXPECTED_HASHES = {
    "stage12660_summary": "2a0047efbf5a6661925e7e6eb945cb82eace0f586187d0b96fefb76fff3564c0",
    "stage12660_matrix": "fc206bfe945481becbc84b19c113b9bc1849e0309941e713feb9e7bfbc74822d",
    "stage12660_candidates": "46963ba6264ae4fc186bf8dba734103db7169361715583339e2a1906285169ad",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12662_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)
UPSTREAM_FALSE_FIELDS = (
    "implementation_ready", "dataset_rows_admitted", "structured_repo_state_rows_admitted",
    "structured_repo_state_admission_ready", "stage12661_allowed", "training_admission_allowed",
    "training_allowed", "training_run_allowed", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "gpu_allocation_requested",
    "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized", "replay_trustworthy",
    "level_3_materialized", "model_execution_authorized_next", "optimizer_step_authorized",
    "source_emission_authorized", "body_emission_authorized",
)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder",
    "TODO", "TBD", "input_text", "target_text", "query_text", "source_lineage", "source_row_id",
)

EXPECTED_SPLITS = {"eval": 315, "strict_eval": 315, "train": 1557}
EXPECTED_OBJECTIVES = {
    "structured_repo_state.evidence_role": 729,
    "structured_repo_state.evidence_route": 729,
    "structured_repo_state.hypothesis_status": 729,
}


class Stage12661AdmissionError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12661AdmissionError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12661AdmissionError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12661AdmissionError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12661AdmissionError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12660_summary", S12660_SUMMARY),
        ("stage12660_matrix", S12660_MATRIX),
        ("stage12660_candidates", S12660_CANDIDATES),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12661AdmissionError("pin_drift:" + label)
    summary = read_json(S12660_SUMMARY)
    matrix = read_json(S12660_MATRIX)
    candidates = read_jsonl(S12660_CANDIDATES)
    check_false(summary, "stage12660_summary", UPSTREAM_FALSE_FIELDS)
    check_false(matrix, "stage12660_matrix", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12661AdmissionError("stage12660_next_action_drift")
    return {"summary": summary, "matrix": matrix, "candidates": candidates}


def review_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "training_candidates", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2187:
        raise Stage12661AdmissionError("candidate_count_drift")
    split_counts = dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))
    objective_counts = dict(sorted(collections.Counter(str(row.get("training_objective")) for row in rows).items()))
    label_counts = dict(sorted(collections.Counter(str(row.get("target_label")) for row in rows).items()))
    root_sets: dict[str, set[str]] = {split: set() for split in EXPECTED_SPLITS}
    for row in rows:
        split = str(row.get("split"))
        root_sets.setdefault(split, set()).add(str(row.get("root_candidate_id")))
        if row.get("training_eligible_candidate") is not True:
            raise Stage12661AdmissionError("non_eligible_candidate")
        if row.get("trainer_consumable") is not False or row.get("row_admitted") is not False:
            raise Stage12661AdmissionError("candidate_preadmitted")
        if row.get("target_label") not in {"teacher_supported", "decisive_evidence", "retrieve_answer_abstain"}:
            raise Stage12661AdmissionError("bad_target_label")
        if not isinstance(row.get("input_state"), dict) or not row["input_state"]:
            raise Stage12661AdmissionError("missing_input_state")
        if row["input_state"].get("repo_family_bucket") == "unknown" or row["input_state"].get("language_family") == "unknown":
            raise Stage12661AdmissionError("missing_root_metadata")
    if split_counts != EXPECTED_SPLITS:
        raise Stage12661AdmissionError("split_count_drift")
    if objective_counts != EXPECTED_OBJECTIVES:
        raise Stage12661AdmissionError("objective_count_drift")
    overlap = {
        "train_eval": len(root_sets["train"] & root_sets["eval"]),
        "train_strict_eval": len(root_sets["train"] & root_sets["strict_eval"]),
        "eval_strict_eval": len(root_sets["eval"] & root_sets["strict_eval"]),
    }
    if any(overlap.values()):
        raise Stage12661AdmissionError("root_split_overlap")
    return {
        "record_type": "stage12661_structured_repo_state_admission_review_audit_v1",
        "review_decision": "ADMIT_STRUCTURED_REPO_STATE_ROWS_FOR_TRAINER_CONSUMPTION_NO_TRAINING_RUN",
        "candidate_rows_reviewed": len(rows),
        "admitted_rows": len(rows),
        "split_counts": split_counts,
        "objective_counts": objective_counts,
        "target_label_counts": label_counts,
        "root_split_overlap_counts": overlap,
        "root_counts_by_split": {split: len(root_sets[split]) for split in sorted(root_sets)},
        "empty_template_marker_scan_passed": True,
        "private_path_scan_passed": True,
        "raw_text_scan_passed": True,
        "trainer_consumable_before_admission": 0,
        "next_required_action": "stage12662_structured_repo_state_training_admission_preflight_only",
        **false_fields(),
    }


def admitted_row(row: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.pop("training_candidate_id", None)
    out.pop("root_candidate_id", None)
    out["trainer_consumable"] = True
    out["row_admitted"] = True
    out["admission_required_before_training"] = False
    out["admission_stage"] = STAGE
    out["loss_weight"] = out.pop("loss_weight_after_admission")
    assert_no_forbidden(out, "admitted_row", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return out


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    audit = review_candidates(loaded["candidates"])
    admitted = [admitted_row(row) for row in loaded["candidates"]]
    matrix = {
        "record_type": "stage12661_structured_repo_state_admission_matrix_v1",
        "stage": STAGE,
        "admitted_rows": len(admitted),
        "trainer_consumable_rows": len(admitted),
        "split_counts": audit["split_counts"],
        "objective_counts": audit["objective_counts"],
        "root_split_overlap_counts": audit["root_split_overlap_counts"],
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "structured_repo_state_admission_ready": True,
        "training_admission_allowed": True,
        "strict_eval_admitted": True,
        "strict_eval_eligible": True,
        **false_fields(),
    }
    summary = {
        "record_type": "stage12661_public_structured_repo_state_admission_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "stage12660_training_eligibility_independently_reviewed": True,
        "admitted_rows": len(admitted),
        "trainer_consumable_rows": len(admitted),
        "split_counts": audit["split_counts"],
        "objective_counts": audit["objective_counts"],
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "structured_repo_state_admission_ready": True,
        "training_admission_allowed": True,
        "strict_eval_admitted": True,
        "strict_eval_eligible": True,
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, admitted


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, admitted = build_packet()
    matrix = {
        "record_type": "stage12661_structured_repo_state_admission_matrix_v1",
        "stage": STAGE,
        "admitted_rows": len(admitted),
        "trainer_consumable_rows": len(admitted),
        "split_counts": audit["split_counts"],
        "objective_counts": audit["objective_counts"],
        "root_split_overlap_counts": audit["root_split_overlap_counts"],
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "structured_repo_state_admission_ready": True,
        "training_admission_allowed": True,
        "strict_eval_admitted": True,
        "strict_eval_eligible": True,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    private = {
        "record_type": "stage12661_private_structured_repo_state_admission_packet_v1",
        "stage": STAGE,
        "stage12660_candidates_sha256": EXPECTED_HASHES["stage12660_candidates"],
        "admitted_rows_sha256": stable_hash(admitted),
        "review_audit_sha256": stable_hash(audit),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12661_structured_repo_state_admission_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "admitted_rows_sha256": stable_hash(admitted),
        "private_packet_sha256": stable_hash(private),
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_allowed": True,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12661_structured_repo_state_admission_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        "admitted_rows_sha256": stable_hash(admitted),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "admission_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "review_audit.json", audit)
    write_json(out / "private/structured_repo_state_admission_packet.json", private)
    write_jsonl(out / "private/admitted_structured_repo_state_rows.jsonl", admitted)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
