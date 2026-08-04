#!/usr/bin/env python3
# Enrich reviewed Structured Repo State candidates and materialize training-eligible candidates without admitting training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12660_structured_repo_state_reviewed_candidate_enrichment_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12659_SUMMARY = ROOT / "runs/summaries/stage12659_structured_repo_state_manifest_independent_review_only.json"
S12659_AUDIT = ROOT / "runs/local/artifacts/stage12659_structured_repo_state_manifest_independent_review_only/review_audit.json"
S12658_MANIFEST = ROOT / "runs/local/artifacts/stage12658_structured_repo_state_sanitized_candidate_manifest_preflight_only/private/sanitized_structured_repo_state_candidate_manifest.jsonl"

EXPECTED_HASHES = {
    "stage12659_summary": "d478c1332a3ede3d366185ebd0a071caa58c60cefe5eafac6233d28e8d0b2005",
    "stage12659_audit": "1d8fbaf4aaf9c8192a0dd2b63760f489e60bd721e5d8d863eeffdd941306be14",
    "stage12658_manifest": "1e55841f0a68433e6ca551cdfcfee2d96b73de121f74a721d50d5093898bd794",
}

FALSE_FIELDS = (
    "implementation_ready", "dataset_rows_admitted", "structured_repo_state_rows_admitted",
    "structured_repo_state_admission_ready", "stage12661_allowed", "training_admission_allowed",
    "training_allowed", "training_run_allowed", "training_admitted", "strict_eval_admitted",
    "sealed_eval_admitted", "strict_eval_eligible", "sealed_eval_eligible", "gpu_allocation_requested",
    "cuda2_training_allowed", "vm_runner_execution_allowed", "runtime_authorized", "replay_trustworthy",
    "level_3_materialized", "model_execution_authorized_next", "optimizer_step_authorized",
    "source_emission_authorized", "body_emission_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12661_allowed") + ("stage12660_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder",
    "TODO", "TBD", "input_text", "target_text", "query_text", "source_lineage", "source_row_id",
)

LOSS_ELIGIBLE_FAMILIES = {"compiled_causal_states", "compiled_multitarget_rows"}
LOSS_FAMILY_BY_LABEL = {
    "teacher_supported": "structured_repo_state.hypothesis_status",
    "decisive_evidence": "structured_repo_state.evidence_role",
    "retrieve_answer_abstain": "structured_repo_state.evidence_route",
}


class Stage12660EnrichmentError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12660EnrichmentError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12660EnrichmentError(f"jsonl_object_required:{path.name}:{line_number}")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...] = FALSE_FIELDS) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12660EnrichmentError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12660EnrichmentError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12659_summary", S12659_SUMMARY),
        ("stage12659_audit", S12659_AUDIT),
        ("stage12658_manifest", S12658_MANIFEST),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12660EnrichmentError("pin_drift:" + label)
    summary = read_json(S12659_SUMMARY)
    audit = read_json(S12659_AUDIT)
    manifest = read_jsonl(S12658_MANIFEST)
    check_false(summary, "stage12659_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12659_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12660EnrichmentError("stage12659_next_action_drift")
    if audit.get("review_decision") != "PASS_AS_SANITIZED_REVIEW_CANDIDATE_MANIFEST_NOT_ADMISSION":
        raise Stage12660EnrichmentError("stage12659_review_not_passed")
    return {"summary": summary, "audit": audit, "manifest": manifest}


def split_for_root(root_candidate_id: str) -> str:
    value = int(hashlib.sha256(root_candidate_id.encode("utf-8")).hexdigest()[:8], 16) % 100
    if value < 70:
        return "train"
    if value < 85:
        return "eval"
    return "strict_eval"


def root_metadata(manifest: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for row in manifest:
        if row.get("source_row_family") != "compiled_root_records":
            continue
        if row.get("eligible_for_stage12659_review") is not True:
            continue
        metadata[str(row["root_candidate_id"])] = {
            "repo_family_bucket": row["repo_family_bucket"],
            "language_family": row["language_family"],
            "root_verifier_family": row.get("sanitized_structural_features", {}).get("verifier_family", "unknown"),
        }
    return metadata


def training_row(row: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    label = str(row.get("state_label_type") or "")
    if label not in LOSS_FAMILY_BY_LABEL:
        raise Stage12660EnrichmentError("unsupported_training_label:" + label)
    enriched = {
        "training_candidate_id": row["candidate_id"],
        "root_candidate_id": row["root_candidate_id"],
        "split": split_for_root(str(row["root_candidate_id"])),
        "curriculum_layer": "structured_repo_state",
        "training_objective": LOSS_FAMILY_BY_LABEL[label],
        "input_state": {
            "repo_family_bucket": metadata["repo_family_bucket"],
            "language_family": metadata["language_family"],
            "root_verifier_family": metadata["root_verifier_family"],
            "source_row_family": row["source_row_family"],
            "state_signal_type": row["state_signal_type"],
            "structural_features": row["sanitized_structural_features"],
        },
        "target_label": label,
        "loss_mask": {"structured_repo_state_ce": 1.0, "decoder_ce": 0.0},
        "training_eligible_candidate": True,
        "trainer_consumable": False,
        "row_admitted": False,
        "loss_weight_after_admission": 1.0,
        "admission_required_before_training": True,
    }
    assert_no_forbidden(enriched, "training_candidate_row", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return enriched


def build_training_candidates(manifest: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    metadata = root_metadata(manifest)
    training_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    for row in manifest:
        if row.get("candidate_status") != "candidate_for_independent_review":
            continue
        root_id = str(row["root_candidate_id"])
        if row.get("source_row_family") == "compiled_root_records":
            support_rows.append({
                "support_candidate_id": row["candidate_id"],
                "root_candidate_id": root_id,
                "split": split_for_root(root_id),
                "support_role": "root_metadata_enrichment_only",
                "repo_family_bucket": row["repo_family_bucket"],
                "language_family": row["language_family"],
                "trainer_consumable": False,
                "row_admitted": False,
            })
            continue
        if row.get("source_row_family") not in LOSS_ELIGIBLE_FAMILIES:
            continue
        if root_id not in metadata:
            raise Stage12660EnrichmentError("missing_root_metadata:" + root_id)
        training_rows.append(training_row(row, metadata[root_id]))
    assert_no_forbidden(training_rows, "training_candidate_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(support_rows, "support_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return training_rows, support_rows


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    loaded = load_inputs()
    training_rows, support_rows = build_training_candidates(loaded["manifest"])
    split_counts = dict(sorted(collections.Counter(row["split"] for row in training_rows).items()))
    objective_counts = dict(sorted(collections.Counter(row["training_objective"] for row in training_rows).items()))
    label_counts = dict(sorted(collections.Counter(row["target_label"] for row in training_rows).items()))
    if len(training_rows) != 2187:
        raise Stage12660EnrichmentError("training_candidate_count_drift")
    if len(support_rows) != 729:
        raise Stage12660EnrichmentError("support_count_drift")
    if split_counts != {"eval": 315, "strict_eval": 315, "train": 1557}:
        raise Stage12660EnrichmentError("split_count_drift")
    if any(row["trainer_consumable"] for row in training_rows):
        raise Stage12660EnrichmentError("trainer_consumable_drift")
    matrix = {
        "record_type": "stage12660_structured_repo_state_training_eligible_candidate_matrix_v1",
        "stage": STAGE,
        "training_eligible_candidate_rows": len(training_rows),
        "root_metadata_support_rows": len(support_rows),
        "trainer_consumable_rows": 0,
        "row_admitted_count": 0,
        "split_counts": split_counts,
        "objective_counts": objective_counts,
        "target_label_counts": label_counts,
        "remaining_blockers": [
            "separate_training_admission_required",
            "strict_eval_and_sealed_eval_not_admitted",
            "trainer_consumable_manifest_not_materialized",
        ],
        "recommended_next_stage": "stage12661_structured_repo_state_training_eligibility_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12660_public_structured_repo_state_training_eligible_candidate_summary_v1",
        "stage": STAGE,
        "decision": "STRUCTURED_REPO_STATE_TRAINING_ELIGIBLE_CANDIDATES_MATERIALIZED_NO_TRAINING_ADMISSION",
        "training_eligibility_materialized": True,
        "training_eligible_candidate_rows": len(training_rows),
        "root_metadata_support_rows": len(support_rows),
        "trainer_consumable_rows": 0,
        "row_admitted_count": 0,
        "split_counts": split_counts,
        "objective_counts": objective_counts,
        "next_required_action": "stage12661_structured_repo_state_training_eligibility_independent_review_only",
        **false_fields(),
    }
    assert_no_forbidden(summary, "summary", PUBLIC_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(matrix, "matrix", PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, matrix, training_rows, support_rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, matrix, training_rows, support_rows = build_packet()
    private = {
        "record_type": "stage12660_private_structured_repo_state_training_eligible_candidate_packet_v1",
        "stage": STAGE,
        "stage12659_summary_sha256": EXPECTED_HASHES["stage12659_summary"],
        "training_candidate_rows_sha256": stable_hash(training_rows),
        "root_metadata_support_rows_sha256": stable_hash(support_rows),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12660_structured_repo_state_training_eligible_candidate_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12659_structured_repo_state_manifest_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12660_structured_repo_state_training_eligible_candidate_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "matrix_sha256": stable_hash(matrix),
        "training_candidate_rows_sha256": stable_hash(training_rows),
        "root_metadata_support_rows_sha256": stable_hash(support_rows),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "training_eligible_candidate_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/structured_repo_state_training_eligible_candidate_packet.json", private)
    write_jsonl(out / "private/training_eligible_structured_repo_state_candidates.jsonl", training_rows)
    write_jsonl(out / "private/root_metadata_support_rows.jsonl", support_rows)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
