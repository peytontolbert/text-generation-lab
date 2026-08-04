#!/usr/bin/env python3
# Compose repo/code and Structured Repo State trainer-consumable rows under one no-training curriculum contract.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12664_repo_code_and_structured_state_pack_composition_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12663_SUMMARY = ROOT / "runs/summaries/stage12663_structured_repo_state_training_admission_independent_review_only.json"
S12663_AUDIT = ROOT / "runs/local/artifacts/stage12663_structured_repo_state_training_admission_independent_review_only/review_audit.json"
S12662_SRS_MANIFEST = ROOT / "runs/local/artifacts/stage12662_structured_repo_state_training_admission_preflight_only/private/structured_repo_state_trainer_manifest.jsonl"
S12656_REPO_MANIFEST = ROOT / "runs/local/artifacts/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only/private/shortcut_resilient_repo_code_curriculum_ingest_manifest.jsonl"
S12656_REPO_EXAMPLES = ROOT / "runs/local/artifacts/stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only/private/shortcut_resilient_repo_code_training_examples.jsonl"

EXPECTED_HASHES = {
    "stage12663_summary": "90d90e4479379a88ef1b4b20d0658e10bf5be0a63e655bf3fd620ae9f8c426fe",
    "stage12663_audit": "7c82c48df495dcb4db58744c97bac96e9102c1be4cc37a422f568551fb9fa543",
    "stage12662_srs_manifest": "bd5045315a9676d9c5e5ce49e11cb9843a524820e6507260e9ed58415bc4acd8",
    "stage12656_repo_manifest": "0e297373cb794dc9c6f22f6c58f9cb5039eb7212de242e67098bffe5822d364e",
    "stage12656_repo_examples": "aa869c73128a7c64868483dd5e3bdb70ab00286f33c4a30d694c4dc4cbc1f872",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12665_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12665_allowed") + ("stage12664_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SRS_SPLITS = {"eval": 315, "strict_eval": 315, "train": 1557}
EXPECTED_REPO_SPLITS = {"eval": 59, "strict_eval": 55, "train": 144}


class Stage12664CompositionError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12664CompositionError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12664CompositionError(f"jsonl_object_required:{path.name}:{line_number}")
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
            raise Stage12664CompositionError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12664CompositionError(f"{label}_leak:{needle}")


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12663_summary", S12663_SUMMARY),
        ("stage12663_audit", S12663_AUDIT),
        ("stage12662_srs_manifest", S12662_SRS_MANIFEST),
        ("stage12656_repo_manifest", S12656_REPO_MANIFEST),
        ("stage12656_repo_examples", S12656_REPO_EXAMPLES),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12664CompositionError("pin_drift:" + label)
    summary = read_json(S12663_SUMMARY)
    audit = read_json(S12663_AUDIT)
    check_false(summary, "stage12663_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12663_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12664CompositionError("stage12663_next_action_drift")
    return {
        "summary": summary,
        "audit": audit,
        "srs_rows": read_jsonl(S12662_SRS_MANIFEST),
        "repo_rows": read_jsonl(S12656_REPO_MANIFEST),
        "repo_examples": read_jsonl(S12656_REPO_EXAMPLES),
    }


def repo_composition_rows(rows: list[dict[str, Any]], examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    example_hashes = {row["example_id"]: row["source_row_sha256"] for row in examples}
    included: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for row in rows:
        if row.get("trainer_consumable") is not True:
            quarantined.append({
                "layer": "repo_code_knowledge",
                "source_ingest_row": row["ingest_row_id"],
                "split": row["split"],
                "training_objective": row["training_objective"],
                "quarantine_reason": row.get("quarantine_reason") or "not_trainer_consumable",
            })
            continue
        if row.get("training_allowed") is not False or row.get("optimizer_step_authorized") is not False:
            raise Stage12664CompositionError("repo_authority_gate_drift")
        if row.get("source_example_id") not in example_hashes:
            raise Stage12664CompositionError("repo_example_pointer_missing")
        included.append({
            "combined_manifest_row_id": f"repo_code_{len(included) + 1:06d}",
            "curriculum_layer": "repo_code_knowledge",
            "split": row["split"],
            "training_objective": row["training_objective"],
            "curriculum_lane": row["curriculum_lane"],
            "source_example_sha256": row["source_example_sha256"],
            "source_row_sha256": row["source_row_sha256"],
            "loss_mask": row["loss_mask"],
            "loss_weight": row["loss_weight"],
            "trainer_consumable": True,
            "row_admitted": True,
            "source_stage": "stage12656_repo_code_symbol_binding_shortcut_resilience_preflight_only",
        })
    assert_no_forbidden(included, "repo_composition_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return included, quarantined


def srs_composition_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    included: list[dict[str, Any]] = []
    for row in rows:
        if row.get("trainer_consumable") is not True or row.get("row_admitted") is not True:
            raise Stage12664CompositionError("srs_row_not_admitted")
        included.append({
            "combined_manifest_row_id": f"structured_state_{len(included) + 1:06d}",
            "curriculum_layer": "structured_repo_state",
            "split": row["split"],
            "training_objective": row["training_objective"],
            "input_state": row["input_state"],
            "target_label": row["target_label"],
            "loss_mask": row["loss_mask"],
            "loss_weight": row["loss_weight"],
            "trainer_consumable": True,
            "row_admitted": True,
            "compact_signature_cross_split_duplicate": row["compact_signature_cross_split_duplicate"],
            "source_stage": "stage12662_structured_repo_state_training_admission_preflight_only",
        })
    assert_no_forbidden(included, "srs_composition_rows", PRIVATE_FORBIDDEN_SUBSTRINGS)
    return included


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def build_composition(inputs: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    repo_rows, repo_quarantined = repo_composition_rows(inputs["repo_rows"], inputs["repo_examples"])
    srs_rows = srs_composition_rows(inputs["srs_rows"])
    if count(repo_rows, "split") != EXPECTED_REPO_SPLITS:
        raise Stage12664CompositionError("repo_split_count_drift")
    if count(srs_rows, "split") != EXPECTED_SRS_SPLITS:
        raise Stage12664CompositionError("srs_split_count_drift")
    combined = repo_rows + srs_rows
    layer_counts = count(combined, "curriculum_layer")
    if layer_counts != {"repo_code_knowledge": 258, "structured_repo_state": 2187}:
        raise Stage12664CompositionError("layer_count_drift")
    matrix = {
        "record_type": "stage12664_repo_code_structured_state_pack_composition_matrix_v1",
        "stage": STAGE,
        "combined_trainer_rows": len(combined),
        "layer_counts": layer_counts,
        "split_counts": count(combined, "split"),
        "objective_counts": count(combined, "training_objective"),
        "repo_code_quarantined_rows_preserved": len(repo_quarantined),
        "structured_state_duplicate_downweighted_rows": sum(1 for row in srs_rows if row["compact_signature_cross_split_duplicate"]),
        "training_pack_composition_preflight_passed": True,
        "next_required_action": "stage12665_combined_curriculum_pack_independent_review_only",
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_materialized": True,
        **false_fields(),
    }
    return combined, repo_quarantined, matrix


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    inputs = load_inputs()
    combined, quarantined, matrix = build_composition(inputs)
    summary = {
        "record_type": "stage12664_public_repo_code_structured_state_pack_composition_summary_v1",
        "stage": STAGE,
        "decision": "REPO_CODE_AND_STRUCTURED_STATE_PACK_COMPOSITION_PREFLIGHT_PASSED_NO_TRAINING_RUN",
        "combined_trainer_rows": len(combined),
        "repo_code_rows": matrix["layer_counts"]["repo_code_knowledge"],
        "structured_repo_state_rows": matrix["layer_counts"]["structured_repo_state"],
        "repo_code_quarantined_rows_preserved": len(quarantined),
        "structured_state_duplicate_downweighted_rows": matrix["structured_state_duplicate_downweighted_rows"],
        "split_counts": matrix["split_counts"],
        "next_required_action": matrix["next_required_action"],
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_materialized": True,
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, matrix, combined, quarantined


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, matrix, combined, quarantined = build_packet()
    private = {
        "record_type": "stage12664_private_repo_code_structured_state_pack_composition_packet_v1",
        "stage": STAGE,
        "combined_manifest_sha256": stable_hash(combined),
        "quarantined_manifest_sha256": stable_hash(quarantined),
        "matrix_sha256": stable_hash(matrix),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12664_repo_code_structured_state_pack_composition_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12663_structured_repo_state_training_admission_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "combined_manifest_sha256": stable_hash(combined),
        "private_packet_sha256": stable_hash(private),
        "dataset_rows_admitted": True,
        "combined_curriculum_pack_materialized": True,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12664_repo_code_structured_state_pack_composition_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "matrix_sha256": stable_hash(matrix),
        "combined_manifest_sha256": stable_hash(combined),
        "quarantined_manifest_sha256": stable_hash(quarantined),
        **false_fields(),
    }
    for label, record in (("summary", summary), ("matrix", matrix), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "summary.json", summary)
    write_json(out / "pack_composition_matrix.json", matrix)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(out / "private/repo_code_structured_state_pack_composition_packet.json", private)
    write_jsonl(out / "private/combined_curriculum_trainer_manifest.jsonl", combined)
    write_jsonl(out / "private/preserved_quarantined_repo_code_rows.jsonl", quarantined)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


def main() -> None:
    print(json.dumps(build(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
