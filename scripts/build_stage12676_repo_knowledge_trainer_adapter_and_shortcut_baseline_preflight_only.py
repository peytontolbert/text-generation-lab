#!/usr/bin/env python3
"""Bind repo-knowledge rows to a trainer-shaped adapter and shortcut policy.

This stage resolves the Stage12675 blockers without authorizing training:
Stage12674 rows are converted to canonical adapter candidates, ultra-common
cross-split target signatures are quarantined, and the remaining repeated
targets are downweighted by a deterministic shortcut baseline.
"""
from __future__ import annotations

import collections
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12676_repo_knowledge_trainer_adapter_and_shortcut_baseline_preflight_only"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

S12675_SUMMARY = ROOT / "runs/summaries/stage12675_real_repo_knowledge_independent_review_only.json"
S12675_AUDIT = ROOT / "runs/local/artifacts/stage12675_real_repo_knowledge_independent_review_only/real_repo_knowledge_independent_review_audit.json"
S12674_ROWS = ROOT / "runs/local/artifacts/stage12674_real_repo_knowledge_materialization_preflight_only/real_repo_knowledge_examples.jsonl"

EXPECTED_HASHES = {
    "stage12675_summary": "8f33d823733ea4d8f4606253aba774fa4796b7df9c3397dac2fc54d027b6d855",
    "stage12675_audit": "1172dafc359da36366186eb11113259fd22144fc9ccfed0688ed36c877b68696",
    "stage12674_rows": "eddca41340146b1910bd771c2bf9b673efa2f0db69b54ebbcf8c8c7acad24558",
}

FALSE_FIELDS = (
    "implementation_ready", "stage12677_allowed", "training_allowed", "training_run_allowed",
    "training_admitted", "gpu_allocation_requested", "cuda2_training_allowed", "vm_runner_execution_allowed",
    "runtime_authorized", "replay_trustworthy", "level_3_materialized", "model_execution_authorized_next",
    "optimizer_step_authorized", "source_emission_authorized", "body_emission_authorized",
    "sealed_eval_admitted", "sealed_eval_eligible", "strict_eval_admitted", "strict_eval_eligible",
    "strict_eval_authorized", "sealed_eval_authorized", "loss_authorized", "compiler_execution_authorized",
)
UPSTREAM_FALSE_FIELDS = tuple(field for field in FALSE_FIELDS if field != "stage12677_allowed") + ("stage12676_allowed",)
ROW_AUTHORITY_FALSE_FIELDS = (
    "training_allowed", "training_run_allowed", "optimizer_step_authorized", "runtime_authorized",
    "source_emission_authorized", "body_emission_authorized", "model_execution_authorized", "loss_authorized",
)
CANONICAL_REQUIRED_FIELDS = {
    "row_id", "split", "language_family", "input_state", "target", "loss_mask", "loss_weight",
    "authority", "source_provenance", "anti_cheat_contract", "adapter_status",
}
FORBIDDEN_SUBSTRINGS = ("/data/", "/arxiv/", "PLACEHOLDER", "placeholder", "TODO", "TBD", "Answer:", "<fill", "\x00")
EXPECTED_OBJECTIVE_COUNTS = {
    "build_file_role_fact": 7068,
    "curriculum_use_presence": 3937,
    "extension_count_fact": 9081,
    "language_count_fact": 2236,
    "primary_language_rank_fact": 1774,
    "readme_doc_surface_fact": 4873,
    "repo_capability_profile": 500,
    "repo_health_bucket_fact": 2000,
}
EXPECTED_SPLIT_COUNTS = {"eval": 6868, "strict_eval": 6338, "train": 18263}
ULTRA_COMMON_CROSS_SPLIT_TARGET_THRESHOLD = 500
MIN_DUPLICATE_TARGET_WEIGHT = 0.05


class Stage12676AdapterError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Stage12676AdapterError("json_object_required:" + path.name)
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Stage12676AdapterError(f"row_object_required:{line_number}")
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


def check_false(record: Mapping[str, Any], label: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        if record.get(field) is not False:
            raise Stage12676AdapterError(f"{label}_gate_drift:{field}")


def assert_no_forbidden(value: Any, label: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True) if not isinstance(value, str) else value
    for needle in FORBIDDEN_SUBSTRINGS:
        if needle in encoded:
            raise Stage12676AdapterError(f"{label}_forbidden_substring:{needle}")


def count(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(collections.Counter(str(row.get(key)) for row in rows).items()))


def target_signature(row: Mapping[str, Any]) -> str:
    return stable_hash({
        "objective_family": row.get("objective_family"),
        "expected_output": row.get("expected_output"),
    })


def authority() -> dict[str, bool]:
    return {field: False for field in ROW_AUTHORITY_FALSE_FIELDS}


def anti_cheat_contract() -> dict[str, bool]:
    return {
        "target_label_not_visible_in_input_state": True,
        "no_raw_source_body": True,
        "no_absolute_path_surface": True,
        "duplicate_target_weight_bound_applied": True,
        "ultra_common_cross_split_targets_quarantined": True,
    }


def load_inputs() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    pins = {
        "stage12675_summary": S12675_SUMMARY,
        "stage12675_audit": S12675_AUDIT,
        "stage12674_rows": S12674_ROWS,
    }
    for label, path in pins.items():
        if sha256_bytes(path.read_bytes()) != EXPECTED_HASHES[label]:
            raise Stage12676AdapterError("pin_drift:" + label)
    summary = read_json(S12675_SUMMARY)
    audit = read_json(S12675_AUDIT)
    check_false(summary, "stage12675_summary", UPSTREAM_FALSE_FIELDS)
    check_false(audit, "stage12675_audit", UPSTREAM_FALSE_FIELDS)
    if summary.get("next_required_action") != STAGE:
        raise Stage12676AdapterError("stage12675_next_action_drift")
    if summary.get("training_admission_review_passed") is not False:
        raise Stage12676AdapterError("stage12675_training_admission_drift")
    rows = read_jsonl(S12674_ROWS)
    if len(rows) != 31469 or count(rows, "objective_family") != EXPECTED_OBJECTIVE_COUNTS or count(rows, "split") != EXPECTED_SPLIT_COUNTS:
        raise Stage12676AdapterError("stage12674_row_count_drift")
    return summary, audit, rows


def shortcut_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[target_signature(row)].append(row)
    return dict(groups)


def quarantine_signatures(groups: Mapping[str, list[dict[str, Any]]]) -> set[str]:
    return {
        signature
        for signature, group in groups.items()
        if len(group) >= ULTRA_COMMON_CROSS_SPLIT_TARGET_THRESHOLD and len({row["split"] for row in group}) > 1
    }


def duplicate_weight(signature_count: int) -> float:
    return round(max(MIN_DUPLICATE_TARGET_WEIGHT, min(1.0, 1.0 / math.sqrt(signature_count))), 6)


def adapt_row(row: Mapping[str, Any], signature: str, signature_count: int) -> dict[str, Any]:
    original_authority = row.get("authority") if isinstance(row.get("authority"), dict) else {}
    if any(original_authority.values()):
        raise Stage12676AdapterError("source_row_authority_open")
    input_state = row.get("knowledge_input") if isinstance(row.get("knowledge_input"), dict) else {}
    expected_output = row.get("expected_output") if isinstance(row.get("expected_output"), dict) else {}
    if not input_state or not expected_output:
        raise Stage12676AdapterError("source_row_missing_knowledge_fields")
    adapted = {
        "row_id": "stage12676_" + str(row["row_id"]).removeprefix("stage12674_"),
        "split": row["split"],
        "language_family": "repo_metadata",
        "input_state": input_state,
        "target": {
            "repo_knowledge_target": expected_output,
            "target_signature": signature[:24],
        },
        "loss_mask": {"repo_knowledge_ce": True},
        "loss_weight": duplicate_weight(signature_count),
        "authority": authority(),
        "source_provenance": {
            "source_stage": "stage12674_real_repo_knowledge_materialization_preflight_only",
            "source_row_digest": stable_hash(row),
            "source_target_signature": signature[:24],
        },
        "anti_cheat_contract": anti_cheat_contract(),
        "adapter_status": "repo_knowledge_adapter_bound_shortcut_weighted_review_required",
        "shortcut_baseline": {
            "target_signature_count": signature_count,
            "weight_policy": "inverse_sqrt_duplicate_target_count_with_floor",
            "quarantine_policy": "ultra_common_cross_split_target_signature",
        },
        "training_allowed": False,
        "training_run_allowed": False,
        "optimizer_step_authorized": False,
    }
    missing = CANONICAL_REQUIRED_FIELDS.difference(adapted)
    if missing:
        raise Stage12676AdapterError("canonical_fields_missing:" + ",".join(sorted(missing)))
    if any(adapted["authority"].values()):
        raise Stage12676AdapterError("adapted_authority_open")
    assert_no_forbidden(adapted, "adapter_row")
    return adapted


def build_adapter(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    groups = shortcut_groups(rows)
    quarantined_signatures = quarantine_signatures(groups)
    adapter_rows: list[dict[str, Any]] = []
    quarantine_rows: list[dict[str, Any]] = []
    for row in rows:
        signature = target_signature(row)
        signature_count = len(groups[signature])
        if signature in quarantined_signatures:
            quarantine_rows.append({
                "source_row_digest": stable_hash(row),
                "split": row["split"],
                "objective_family": row["objective_family"],
                "target_signature": signature[:24],
                "target_signature_count": signature_count,
                "quarantine_reason": "ultra_common_cross_split_target_signature",
            })
            continue
        adapter_rows.append(adapt_row(row, signature, signature_count))

    target_duplicate_instances = sum(len(group) - 1 for group in groups.values() if len(group) > 1)
    target_duplicate_signatures_cross_split = sum(1 for group in groups.values() if len({row["split"] for row in group}) > 1)
    effective_weighted_rows = round(sum(float(row["loss_weight"]) for row in adapter_rows), 6)
    adapter_objective_counts = dict(sorted(collections.Counter(row["input_state"]["objective_family"] for row in adapter_rows).items()))
    shortcut_audit = {
        "record_type": "stage12676_shortcut_baseline_audit_v1",
        "stage": STAGE,
        "source_rows_reviewed": len(rows),
        "target_signature_count": len(groups),
        "target_duplicate_instances_before_policy": target_duplicate_instances,
        "target_duplicate_signatures_cross_split_before_policy": target_duplicate_signatures_cross_split,
        "quarantine_threshold": ULTRA_COMMON_CROSS_SPLIT_TARGET_THRESHOLD,
        "quarantined_target_signatures": len(quarantined_signatures),
        "quarantined_rows": len(quarantine_rows),
        "adapter_candidate_rows": len(adapter_rows),
        "effective_weighted_rows": effective_weighted_rows,
        "minimum_loss_weight": min(float(row["loss_weight"]) for row in adapter_rows),
        "maximum_loss_weight": max(float(row["loss_weight"]) for row in adapter_rows),
        "split_counts": count(adapter_rows, "split"),
        "objective_counts": adapter_objective_counts,
        "training_source_rows_admitted": 0,
        **false_fields(),
    }
    if len(adapter_rows) < 25000:
        raise Stage12676AdapterError("adapter_rows_below_required_scale")
    if not 4000 <= effective_weighted_rows <= 5000:
        raise Stage12676AdapterError("effective_weighted_rows_out_of_expected_bound")
    if len(quarantine_rows) != 2851:
        raise Stage12676AdapterError("quarantine_policy_count_drift")
    return adapter_rows, quarantine_rows, shortcut_audit


def build_packet() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    _summary75, _audit75, rows = load_inputs()
    adapter_rows, quarantine_rows, shortcut_audit = build_adapter(rows)
    adapter_split_counts = count(adapter_rows, "split")
    adapter_objective_counts = dict(sorted(collections.Counter(row["input_state"]["objective_family"] for row in adapter_rows).items()))
    loss_counts = dict(sorted(collections.Counter(next(key for key, value in row["loss_mask"].items() if value) for row in adapter_rows).items()))
    audit = {
        "record_type": "stage12676_repo_knowledge_adapter_and_shortcut_audit_v1",
        "stage": STAGE,
        "decision": "REPO_KNOWLEDGE_ADAPTER_AND_SHORTCUT_POLICY_MATERIALIZED_REVIEW_REQUIRED",
        "stage12675_blockers_resolved": {
            "trainer_adapter_fit": "resolved_canonical_repo_knowledge_ce_adapter_candidates_materialized",
            "shortcut_baseline_status": "resolved_ultra_common_quarantine_and_duplicate_target_weighting_materialized",
        },
        "source_rows_reviewed": len(rows),
        "adapter_candidate_rows": len(adapter_rows),
        "quarantined_rows": len(quarantine_rows),
        "effective_weighted_rows": shortcut_audit["effective_weighted_rows"],
        "adapter_split_counts": adapter_split_counts,
        "adapter_objective_counts": adapter_objective_counts,
        "enabled_loss_counts": loss_counts,
        "trainer_adapter_fit": "repo_knowledge_ce_adapter_bound_review_required",
        "shortcut_baseline_status": "materialized_review_required",
        "training_source_rows_admitted": 0,
        "next_required_action": "stage12677_repo_knowledge_adapter_independent_review_only",
        **false_fields(),
    }
    summary = {
        "record_type": "stage12676_public_repo_knowledge_adapter_shortcut_summary_v1",
        "stage": STAGE,
        "decision": audit["decision"],
        "source_rows_reviewed": len(rows),
        "adapter_candidate_rows": len(adapter_rows),
        "quarantined_rows": len(quarantine_rows),
        "effective_weighted_rows": shortcut_audit["effective_weighted_rows"],
        "adapter_split_counts": adapter_split_counts,
        "objective_family_count": len(adapter_objective_counts),
        "enabled_loss_counts": loss_counts,
        "training_source_rows_admitted": 0,
        "next_required_action": audit["next_required_action"],
        **false_fields(),
    }
    for label, record in (("summary", summary), ("audit", audit), ("shortcut_audit", shortcut_audit)):
        assert_no_forbidden(record, label)
    return summary, audit, shortcut_audit, adapter_rows, quarantine_rows


def build(out: Path = OUT, summary_path: Path = SUMMARY) -> dict[str, Any]:
    summary, audit, shortcut_audit, adapter_rows, quarantine_rows = build_packet()
    private = {
        "record_type": "stage12676_private_repo_knowledge_adapter_packet_v1",
        "stage": STAGE,
        "input_hashes": EXPECTED_HASHES,
        "adapter_rows_sha256": stable_hash(adapter_rows),
        "quarantine_rows_sha256": stable_hash(quarantine_rows),
        "audit_sha256": stable_hash(audit),
        "shortcut_audit_sha256": stable_hash(shortcut_audit),
        **false_fields(),
    }
    contract = {
        "record_type": "stage12676_repo_knowledge_adapter_contract_v1",
        "stage": STAGE,
        "decision": summary["decision"],
        "adapter_candidate_rows": summary["adapter_candidate_rows"],
        "quarantined_rows": summary["quarantined_rows"],
        "effective_weighted_rows": summary["effective_weighted_rows"],
        "adapter_rows_sha256": stable_hash(adapter_rows),
        "recommended_next_stage": summary["next_required_action"],
        **false_fields(),
    }
    pointer = {
        "record_type": "stage12676_digest_pointer_v1",
        "stage": STAGE,
        "summary_sha256": stable_hash(summary),
        "contract_sha256": stable_hash(contract),
        "private_packet_sha256": stable_hash(private),
        "audit_sha256": stable_hash(audit),
        "shortcut_audit_sha256": stable_hash(shortcut_audit),
        "adapter_rows_sha256": stable_hash(adapter_rows),
        "quarantine_rows_sha256": stable_hash(quarantine_rows),
        **false_fields(),
    }
    for label, record in (("private", private), ("contract", contract), ("pointer", pointer)):
        assert_no_forbidden(record, label)
    write_jsonl(out / "private/repo_knowledge_adapter_candidates.jsonl", adapter_rows)
    write_jsonl(out / "private/repo_knowledge_shortcut_quarantine.jsonl", quarantine_rows)
    write_json(out / "summary.json", summary)
    write_json(out / "repo_knowledge_adapter_audit.json", audit)
    write_json(out / "repo_knowledge_shortcut_baseline_audit.json", shortcut_audit)
    write_json(out / "private/repo_knowledge_adapter_packet.json", private)
    write_json(out / "contract.json", contract)
    write_json(out / "digest_pointer.json", pointer)
    write_json(summary_path, summary)
    fsync_dir(out)
    fsync_dir(out / "private")
    fsync_dir(summary_path.parent)
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=True))
