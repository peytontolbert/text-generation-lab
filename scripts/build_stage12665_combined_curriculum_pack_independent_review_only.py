#!/usr/bin/env python3
# Independently review the combined repo/code + Structured Repo State curriculum pack without training execution.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12665_combined_curriculum_pack_independent_review_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12664_SUMMARY = ROOT / "runs/summaries/stage12664_repo_code_and_structured_state_pack_composition_preflight_only.json"
S12664_MATRIX = ROOT / "runs/local/artifacts/stage12664_repo_code_and_structured_state_pack_composition_preflight_only/pack_composition_matrix.json"
S12664_COMBINED = ROOT / "runs/local/artifacts/stage12664_repo_code_and_structured_state_pack_composition_preflight_only/private/combined_curriculum_trainer_manifest.jsonl"
S12664_QUARANTINED = ROOT / "runs/local/artifacts/stage12664_repo_code_and_structured_state_pack_composition_preflight_only/private/preserved_quarantined_repo_code_rows.jsonl"

EXPECTED_HASHES = {
    "stage12664_summary": "2db3a9f9a73561c30eb7e11ea10ed635e9179cfc8a2ec8ab78921d81b4a8cd1d",
    "stage12664_matrix": "ef0fbc03f3e578e45790165ad9aa432ce2720b241e24eeadc36feb31a68c40e1",
    "stage12664_combined": "52298e8c5c94e64377b8e251217e2116fcb6d92bcfa6fa21f980c8d17d5f7323",
    "stage12664_quarantined": "e7b3540a5d70718ff8f2bef3088b59d9e59c91d639816c597a0cf1b3cf0aff5c",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12666_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12666_allowed") + ("stage12665_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_LAYER_COUNTS = {"repo_code_knowledge": 258, "structured_repo_state": 2187}
EXPECTED_SPLITS = {"eval": 374, "strict_eval": 370, "train": 1701}
EXPECTED_OBJECTIVES = {
    "repo_code_capability_ce": 200,
    "source_backed_symbol_binding_ce": 58,
    "structured_repo_state.evidence_role": 729,
    "structured_repo_state.evidence_route": 729,
    "structured_repo_state.hypothesis_status": 729,
}


class Stage12665ReviewError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12665ReviewError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12665ReviewError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12665ReviewError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12665ReviewError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12664_summary", S12664_SUMMARY),
        ("stage12664_matrix", S12664_MATRIX),
        ("stage12664_combined", S12664_COMBINED),
        ("stage12664_quarantined", S12664_QUARANTINED),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12665ReviewError("pin_drift:" + label)
    summary = read_json(S12664_SUMMARY)
    matrix = read_json(S12664_MATRIX)
    check_false(summary, "stage12664_summary", UPSTREAM_FALSE_FIELDS)
    check_false(matrix, "stage12664_matrix", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12665ReviewError("stage12664_next_action_drift")
    return {"summary": summary, "matrix": matrix, "combined": read_jsonl(S12664_COMBINED), "quarantined": read_jsonl(S12664_QUARANTINED)}


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def review_combined(rows: list[dict[str, Any]], quarantined: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "combined_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    assert_no_forbidden(quarantined, "quarantined_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2445:
        raise Stage12665ReviewError("combined_count_drift")
    if len(quarantined) != 22:
        raise Stage12665ReviewError("quarantine_count_drift")
    layer_counts = count(rows, "curriculum_layer")
    split_counts = count(rows, "split")
    objective_counts = count(rows, "training_objective")
    if layer_counts != EXPECTED_LAYER_COUNTS:
        raise Stage12665ReviewError("layer_count_drift")
    if split_counts != EXPECTED_SPLITS:
        raise Stage12665ReviewError("split_count_drift")
    if objective_counts != EXPECTED_OBJECTIVES:
        raise Stage12665ReviewError("objective_count_drift")
    if any(row.get("trainer_consumable") is not True or row.get("row_admitted") is not True for row in rows):
        raise Stage12665ReviewError("row_consumable_drift")
    if any(row.get("training_objective") != "source_backed_symbol_binding_ce" for row in quarantined):
        raise Stage12665ReviewError("unexpected_quarantine_family")
    srs_duplicates = sum(1 for row in rows if row.get("curriculum_layer") == "structured_repo_state" and row.get("compact_signature_cross_split_duplicate") is True)
    if srs_duplicates != 1686:
        raise Stage12665ReviewError("srs_duplicate_count_drift")
    return {
        "record_type": "stage12665_combined_curriculum_pack_review_audit_v1",
        "review_decision": "PASS_COMBINED_CURRICULUM_PACK_COMPOSITION_NO_TRAINING_RUN",
        "combined_trainer_rows_reviewed": len(rows),
        "repo_code_rows_reviewed": layer_counts["repo_code_knowledge"],
        "structured_repo_state_rows_reviewed": layer_counts["structured_repo_state"],
        "repo_code_quarantined_rows_preserved": len(quarantined),
        "split_counts": split_counts,
        "objective_counts": objective_counts,
        "structured_state_duplicate_downweighted_rows": srs_duplicates,
        "repo_code_symbol_quarantine_preserved": True,
        "private_path_scan_passed": True,
        "raw_text_scan_passed": True,
        "empty_template_marker_scan_passed": True,
        "stable_candidate_id_scan_passed": True,
        "next_required_action": "stage12666_combined_curriculum_training_authorization_preflight_only",
        **false_fields(),
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    audit = review_combined(loaded["combined"], loaded["quarantined"])
    checks = [
        {"check_id": "stage12664_pins", "status": "pass"},
        {"check_id": "combined_counts", "status": "pass"},
        {"check_id": "quarantine_preservation", "status": "pass"},
        {"check_id": "structured_duplicate_downweight_policy", "status": "pass"},
        {"check_id": "sanitization", "status": "pass"},
        {"check_id": "training_execution_authority", "status": "blocked", "detail": "training run still requires separate authorization"},
    ]
    summary = {
        "record_type": "stage12665_public_combined_curriculum_pack_review_summary_v1",
        "stage": STAGE,
        "decision": audit["review_decision"],
        "combined_curriculum_pack_independently_reviewed": True,
        "combined_trainer_rows_reviewed": audit["combined_trainer_rows_reviewed"],
        "repo_code_rows_reviewed": audit["repo_code_rows_reviewed"],
        "structured_repo_state_rows_reviewed": audit["structured_repo_state_rows_reviewed"],
        "repo_code_quarantined_rows_preserved": audit["repo_code_quarantined_rows_preserved"],
        "structured_state_duplicate_downweighted_rows": audit["structured_state_duplicate_downweighted_rows"],
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_review_passed": True,
        **false_fields(),
    }
    matrix = {
        "record_type": "stage12665_combined_curriculum_pack_review_matrix_v1",
        "stage": STAGE,
        "review_checks": checks,
        "split_counts": audit["split_counts"],
        "objective_counts": audit["objective_counts"],
        "next_required_action": audit["next_required_action"],
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_review_passed": True,
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12665_private_combined_curriculum_pack_review_packet_v1",
        "stage": STAGE,
        "stage12664_combined_manifest_sha256": EXPECTED_HASHES["stage12664_combined"],
        "review_audit_sha256": stable_hash(audit),
        "review_checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12665_combined_curriculum_pack_review_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12664_repo_code_and_structured_state_pack_composition_preflight_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "review_audit_sha256": stable_hash(audit),
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_review_passed": True,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12665_combined_curriculum_pack_review_digest_pointer_v1",
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
    write_json(out / "private/combined_curriculum_pack_review_packet.json", private)
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
