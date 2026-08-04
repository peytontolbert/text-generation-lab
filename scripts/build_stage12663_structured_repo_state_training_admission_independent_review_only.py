#!/usr/bin/env python3
# Independently review the Stage12662 Structured Repo State training-admission preflight without launching training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12663_structured_repo_state_training_admission_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12662_SUMMARY = ROOT / "runs/summaries/stage12662_structured_repo_state_training_admission_preflight_only.json"
S12662_MATRIX = ROOT / "runs/local/artifacts/stage12662_structured_repo_state_training_admission_preflight_only/training_admission_matrix.json"
S12662_MANIFEST = ROOT / "runs/local/artifacts/stage12662_structured_repo_state_training_admission_preflight_only/private/structured_repo_state_trainer_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12662_summary": "fba04d4834d0601fd71d9d37fb162ef2aa023c7f0f40b7f414029d74fbf1210a",
    "stage12662_matrix": "64c51c55c40a2052d05398d5e3850149177f92102b5139bb94efaf21b078e8b7",
    "stage12662_manifest": "bd5045315a9676d9c5e5ce49e11cb9843a524820e6507260e9ed58415bc4acd8",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12664_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12664_allowed") + ("stage12663_allowed",)

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


class Stage12663ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12663ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12663ReviewError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12663ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12663ReviewError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12662_summary", S12662_SUMMARY),
        ("stage12662_matrix", S12662_MATRIX),
        ("stage12662_manifest", S12662_MANIFEST),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12663ReviewError("pin_drift:" + label)
    summary = read_json(S12662_SUMMARY)
    matrix = read_json(S12662_MATRIX)
    manifest = read_jsonl(S12662_MANIFEST)
    check_false(summary, "stage12662_summary", UPSTREAM_FALSE_FIELDS)
    check_false(matrix, "stage12662_matrix", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12663ReviewError("stage12662_next_action_drift")
    return {"summary": summary, "matrix": matrix, "manifest": manifest}


def duplicate_signature_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    signatures: dict[str, set[str]] = collections.defaultdict(set)
    row_counts: collections.Counter[str] = collections.Counter()
    for row in rows:
        signature = stable_hash({
            "input_state": row["input_state"],
            "target_label": row["target_label"],
            "training_objective": row["training_objective"],
        })
        signatures[signature].add(str(row["split"]))
        row_counts[signature] += 1
    cross = {signature for signature, splits in signatures.items() if len(splits) > 1}
    expected_duplicate_rows = sum(row_counts[signature] for signature in cross)
    observed_duplicate_rows = sum(1 for row in rows if row.get("compact_signature_cross_split_duplicate") is True)
    observed_downweighted = sum(1 for row in rows if row.get("loss_weight") == 0.25)
    full_weight = sum(1 for row in rows if row.get("loss_weight") == 1.0)
    if observed_duplicate_rows != expected_duplicate_rows or observed_downweighted != expected_duplicate_rows:
        raise Stage12663ReviewError("duplicate_downweight_policy_drift")
    if full_weight + observed_downweighted != len(rows):
        raise Stage12663ReviewError("loss_weight_partition_drift")
    return {
        "cross_split_duplicate_compact_signature_groups": len(cross),
        "cross_split_duplicate_compact_signature_rows": expected_duplicate_rows,
        "downweighted_rows": observed_downweighted,
        "full_weight_rows": full_weight,
        "duplicate_loss_weight": 0.25,
    }


def review_manifest(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "trainer_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2187:
        raise Stage12663ReviewError("manifest_count_drift")
    split_counts = dict(sorted(collections.Counter(str(row.get("split")) for row in rows).items()))
    objective_counts = dict(sorted(collections.Counter(str(row.get("training_objective")) for row in rows).items()))
    label_counts = dict(sorted(collections.Counter(str(row.get("target_label")) for row in rows).items()))
    if split_counts != EXPECTED_SPLITS:
        raise Stage12663ReviewError("split_count_drift")
    if objective_counts != EXPECTED_OBJECTIVES:
        raise Stage12663ReviewError("objective_count_drift")
    for row in rows:
        if row.get("trainer_consumable") is not True or row.get("row_admitted") is not True:
            raise Stage12663ReviewError("row_not_consumable_or_admitted")
        if row.get("loss_mask") != {"decoder_ce": 0.0, "structured_repo_state_ce": 1.0}:
            raise Stage12663ReviewError("loss_mask_drift")
        if "root_candidate_id" in row or "training_candidate_id" in row:
            raise Stage12663ReviewError("stable_candidate_id_leak")
    duplicate_audit = duplicate_signature_audit(rows)
    return {
        "record_type": "stage12663_structured_repo_state_training_admission_review_audit_v1",
        "review_decision": "PASS_STRUCTURED_REPO_STATE_TRAINING_ADMISSION_PREFLIGHT_NO_TRAINING_RUN",
        "manifest_rows_reviewed": len(rows),
        "trainer_consumable_rows_reviewed": len(rows),
        "split_counts": split_counts,
        "objective_counts": objective_counts,
        "target_label_counts": label_counts,
        **duplicate_audit,
        "empty_template_marker_scan_passed": True,
        "private_path_scan_passed": True,
        "raw_text_scan_passed": True,
        "stable_candidate_id_scan_passed": True,
        "repo_code_pack_merge_required_before_combined_curriculum": True,
        "next_required_action": "stage12664_repo_code_and_structured_state_pack_composition_preflight_only",
        **false_fields(),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    audit = review_manifest(loaded["manifest"])
    checks = [
        {"check_id": "stage12662_pins", "status": "pass"},
        {"check_id": "trainer_manifest_sanitization", "status": "pass"},
        {"check_id": "split_and_objective_counts", "status": "pass"},
        {"check_id": "duplicate_signature_downweight_policy", "status": "pass"},
        {"check_id": "execution_authority", "status": "pass"},
        {"check_id": "combined_pack_composition", "status": "blocked", "detail": "repo/code layer merge is separate"},
    ]
    summary = {
        "record_type": "stage12663_public_structured_repo_state_training_admission_review_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "stage12662_training_admission_preflight_independently_reviewed": True,
        "structured_repo_state_training_pack_review_passed": True,
        "manifest_rows_reviewed": audit["manifest_rows_reviewed"],
        "trainer_consumable_rows_reviewed": audit["trainer_consumable_rows_reviewed"],
        "cross_split_duplicate_compact_signature_rows": audit["cross_split_duplicate_compact_signature_rows"],
        "downweighted_rows": audit["downweighted_rows"],
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_review_passed": True,
        **false_fields(),
    }
    matrix = {
        "record_type": "stage12663_structured_repo_state_training_admission_review_matrix_v1",
        "stage": STAGE,
        "review_checks": checks,
        "split_counts": audit["split_counts"],
        "objective_counts": audit["objective_counts"],
        "duplicate_signature_policy": {
            "cross_split_duplicate_compact_signature_groups": audit["cross_split_duplicate_compact_signature_groups"],
            "cross_split_duplicate_compact_signature_rows": audit["cross_split_duplicate_compact_signature_rows"],
            "duplicate_loss_weight": audit["duplicate_loss_weight"],
        },
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_review_passed": True,
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12663_private_structured_repo_state_training_admission_review_packet_v1",
        "stage": STAGE,
        "stage12662_manifest_sha256": EXPECTED_HASHES["stage12662_manifest"],
        "review_audit_sha256": stable_hash(audit),
        "review_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12663_structured_repo_state_training_admission_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12662_structured_repo_state_training_admission_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        "dataset_rows_admitted": True,
        "structured_repo_state_rows_admitted": True,
        "training_admission_review_passed": True,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12663_structured_repo_state_training_admission_review_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        "review_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("contract", contract), ("pointer", pointer), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "review_audit.json", audit)
    write_json(out / "private/structured_repo_state_training_admission_review_packet.json", private)
    write_jsonl(out / "private/review_checks.jsonl", checks)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
