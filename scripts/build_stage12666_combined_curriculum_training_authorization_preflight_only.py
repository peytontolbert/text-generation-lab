#!/usr/bin/env python3
# Check whether the reviewed combined curriculum pack is trainer-authorizable without launching training.
from __future__ import annotations

import collections
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12666_combined_curriculum_training_authorization_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12665_SUMMARY = ROOT / "runs/summaries/stage12665_combined_curriculum_pack_independent_review_only.json"
S12665_AUDIT = ROOT / "runs/local/artifacts/stage12665_combined_curriculum_pack_independent_review_only/review_audit.json"
S12664_COMBINED = ROOT / "runs/local/artifacts/stage12664_repo_code_and_structured_state_pack_composition_preflight_only/private/combined_curriculum_trainer_manifest.jsonl"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
MANIFEST_SCHEMA = ROOT / "configs/schema/manifest_row.schema.json"

EXPECTED_HASHES = {
    "stage12665_summary": "526db4073a6dcb26b9b807a888142998c7b69e4b22c4a74835069a8abd1de7a1",
    "stage12665_audit": "aa06f5690f7f7b60b79d9c4d9053c9f5c13f443e787a9d581d2bb67e0c056f89",
    "stage12664_combined": "52298e8c5c94e64377b8e251217e2116fcb6d92bcfa6fa21f980c8d17d5f7323",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12667_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field not in {"stage12667_allowed", "strict_eval_admitted"}) + ("stage12666_allowed",)

PUBLIC_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "input_text", "target_text", "query_text", "model_input", "root_id", "state_id",
    "episode_id", "source_lineage", "source_row_id", "jsonl", "placeholder", "PLACEHOLDER", "TODO", "TBD",
)
PRIVATE_FORBIDDEN_SUBSTRINGS = (
    "/data/", "/arxiv/", "\x00", "Answer: placeholder", "PLACEHOLDER", "placeholder", "TODO", "TBD",
    "input_text", "target_text", "query_text", "model_input", "source_lineage", "source_row_id",
    "root_candidate_id", "training_candidate_id",
)

EXPECTED_SPLITS = {"eval": 374, "strict_eval": 370, "train": 1701}
EXPECTED_LAYERS = {"repo_code_knowledge": 258, "structured_repo_state": 2187}
EXPECTED_OBJECTIVES = {
    "repo_code_capability_ce": 200,
    "source_backed_symbol_binding_ce": 58,
    "structured_repo_state.evidence_role": 729,
    "structured_repo_state.evidence_route": 729,
    "structured_repo_state.hypothesis_status": 729,
}
CANONICAL_REQUIRED_FIELDS = {
    "row_id", "split", "language_family", "input_state", "target", "loss_mask",
    "authority", "source_provenance", "anti_cheat_contract",
}


class Stage12666PreflightError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12666PreflightError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12666PreflightError(f"row_object_required:{line_number}")
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
            raise Stage12666PreflightError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str, needles: tuple[str, ...]) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in needles:
        if needle in encoded:
            raise Stage12666PreflightError(f"{label}_leak:{needle}")


def count(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def load_inputs() -> dict[str, Any]:
    for label, path in (
        ("stage12665_summary", S12665_SUMMARY),
        ("stage12665_audit", S12665_AUDIT),
        ("stage12664_combined", S12664_COMBINED),
    ):
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12666PreflightError("pin_drift:" + label)
    summary = read_json(S12665_SUMMARY)
    audit = read_json(S12665_AUDIT)
    check_false(summary, "stage12665_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12665_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12666PreflightError("stage12665_next_action_drift")
    return {"summary": summary, "audit": audit, "rows": read_jsonl(S12664_COMBINED)}


def row_schema_fingerprint(rows: list[dict[str, Any]]) -> dict[str, Any]:
    schema_counts = collections.Counter(tuple(sorted(row.keys())) for row in rows)
    fingerprints = []
    for index, (keys, row_count) in enumerate(sorted(schema_counts.items(), key=lambda item: (-item[1], item[0])), start=1):
        fingerprints.append({
            "schema_index": index,
            "row_count": row_count,
            "field_count": len(keys),
            "field_set_sha256": stable_hash(list(keys)),
            "canonical_required_missing": sorted(CANONICAL_REQUIRED_FIELDS.difference(keys)),
        })
    return {
        "distinct_schema_count": len(schema_counts),
        "schemas": fingerprints,
        "all_rows_match_canonical_manifest_schema": all(not item["canonical_required_missing"] for item in fingerprints),
    }


def objective_support_report() -> dict[str, Any]:
    trainer_text = TRAINER.read_text(encoding="utf-8")
    loop_text = TRAINING_LOOP.read_text(encoding="utf-8")
    schema = read_json(MANIFEST_SCHEMA)
    corpus = trainer_text + "\n" + loop_text
    objectives = {
        objective: objective in corpus
        for objective in EXPECTED_OBJECTIVES
    }
    loss_keys = {
        "symbol_binding_ce": "symbol_binding_ce" in corpus,
        "structured_repo_state_ce": "structured_repo_state_ce" in corpus,
        "repo_code_capability_ce": "repo_code_capability_ce" in corpus,
        "source_backed_symbol_binding_ce": "source_backed_symbol_binding_ce" in corpus,
    }
    required = set(schema.get("required") or [])
    return {
        "trainer_sha256": sha256_bytes(TRAINER.read_bytes()),
        "training_loop_sha256": sha256_bytes(TRAINING_LOOP.read_bytes()),
        "manifest_schema_sha256": sha256_bytes(MANIFEST_SCHEMA.read_bytes()),
        "canonical_schema_required_fields_match_expected": required == CANONICAL_REQUIRED_FIELDS,
        "objective_literals_supported": objectives,
        "loss_literal_support": loss_keys,
        "combined_manifest_requires_adapter": not all(objectives.values()),
    }


def audit_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    assert_no_forbidden(rows, "combined_manifest", PRIVATE_FORBIDDEN_SUBSTRINGS)
    if len(rows) != 2445:
        raise Stage12666PreflightError("combined_row_count_drift")
    split_counts = count(rows, "split")
    layer_counts = count(rows, "curriculum_layer")
    objective_counts = count(rows, "training_objective")
    if split_counts != EXPECTED_SPLITS:
        raise Stage12666PreflightError("split_count_drift")
    if layer_counts != EXPECTED_LAYERS:
        raise Stage12666PreflightError("layer_count_drift")
    if objective_counts != EXPECTED_OBJECTIVES:
        raise Stage12666PreflightError("objective_count_drift")
    if any(row.get("trainer_consumable") is not True or row.get("row_admitted") is not True for row in rows):
        raise Stage12666PreflightError("row_admission_drift")
    if sum(1 for row in rows if row.get("compact_signature_cross_split_duplicate") is True) != 1686:
        raise Stage12666PreflightError("structured_duplicate_policy_drift")
    return {
        "combined_rows_checked": len(rows),
        "split_counts": split_counts,
        "layer_counts": layer_counts,
        "objective_counts": objective_counts,
        "all_rows_admitted": True,
        "all_rows_marked_trainer_consumable_by_dataset_stage": True,
        "structured_duplicate_downweighted_rows": 1686,
    }


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    loaded = load_inputs()
    row_audit = audit_rows(loaded["rows"])
    schema_report = row_schema_fingerprint(loaded["rows"])
    support = objective_support_report()
    blockers = []
    if not schema_report["all_rows_match_canonical_manifest_schema"]:
        blockers.append("combined_rows_do_not_match_canonical_trainer_manifest_schema")
    if support["combined_manifest_requires_adapter"]:
        blockers.append("trainer_objective_adapter_required_for_combined_curriculum")
    decision = "BLOCKED_TRAINER_CONTRACT_ADAPTER_REQUIRED"
    audit = {
        "record_type": "stage12666_training_authorization_preflight_audit_v1",
        "stage": STAGE,
        "decision": decision,
        "combined_curriculum_pack_reviewed": True,
        "combined_rows_checked": row_audit["combined_rows_checked"],
        "split_counts": row_audit["split_counts"],
        "layer_counts": row_audit["layer_counts"],
        "objective_counts": row_audit["objective_counts"],
        "schema_report": schema_report,
        "trainer_contract_support": support,
        "authorization_blockers": blockers,
        "training_authorization_preflight_passed": False,
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "training_run_authorization_required": True,
        "cuda_policy_if_later_authorized": "CUDA:2 only; GPUs 0 and 1 reserved",
        "next_required_action": "stage12667_combined_curriculum_trainer_contract_adapter_preflight_only",
        **false_fields(),
    }
    checks = [
        {"check_id": "stage12665_pins", "status": "pass"},
        {"check_id": "combined_pack_counts", "status": "pass"},
        {"check_id": "combined_pack_sanitization", "status": "pass"},
        {"check_id": "canonical_manifest_schema_binding", "status": "blocked", "detail": blockers[0]},
        {"check_id": "trainer_objective_binding", "status": "blocked", "detail": blockers[-1]},
        {"check_id": "training_execution_authority", "status": "blocked", "detail": "separate explicit training-run authorization remains required"},
    ]
    summary = {
        "record_type": "stage12666_public_training_authorization_preflight_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "combined_rows_checked": row_audit["combined_rows_checked"],
        "repo_code_rows": row_audit["layer_counts"]["repo_code_knowledge"],
        "structured_repo_state_rows": row_audit["layer_counts"]["structured_repo_state"],
        "split_counts": row_audit["split_counts"],
        "dataset_rows_admitted": True,
        "combined_dataset_rows_admitted": True,
        "training_authorization_preflight_passed": False,
        "authorization_blockers": blockers,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", audit)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    return summary, audit, checks


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, checks = build_packet()
    private = {
        "record_type": "stage12666_private_training_authorization_preflight_packet_v1",
        "stage": STAGE,
        "stage12665_summary_sha256": EXPECTED_HASHES["stage12665_summary"],
        "stage12665_audit_sha256": EXPECTED_HASHES["stage12665_audit"],
        "combined_manifest_sha256": EXPECTED_HASHES["stage12664_combined"],
        "audit_sha256": stable_hash(audit),
        "checks_sha256": stable_hash(checks),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12666_training_authorization_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "upstream_stage": "stage12665_combined_curriculum_pack_independent_review_only",
        "recommended_next_stage": summary["next_required_action"],
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "dataset_rows_admitted": True,
        "training_authorization_preflight_passed": False,
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12666_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        **false_fields(),
    }
    for label, record in (("contract", contract), ("pointer", pointer), ("private", private)):
        assert_no_forbidden(record, label, PUBLIC_FORBIDDEN_SUBSTRINGS)
    write_json(out / "summary.json", summary)
    write_json(out / "authorization_audit.json", audit)
    write_jsonl(out / "private/authorization_checks.jsonl", checks)
    write_json(out / "private/training_authorization_preflight_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
