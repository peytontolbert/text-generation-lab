#!/usr/bin/env python3
"""Build private causal evidence acquisition work orders.

Stage12515 consumes Stage12514 revalidation records and creates bounded work
orders for future private reviewers/extractors to acquire independent causal
evidence. It is not a renderer, extractor, candidate-return writer, admission
stage, or training package.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12515_private_causal_evidence_acquisition_work_orders"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12514 = "stage12514_causal_proof_revalidation_gate"
REVALIDATION = ROOT / "runs/local/artifacts" / STAGE12514 / "causal_proof_revalidation_records.jsonl"

SLOT_REQUIREMENTS = {
    "same_source_causal_lineage_with_independent_evidence_digest": {
        "proof_class": "same_source_causal_lineage",
        "must_prove": ["same_root_or_repo_context", "same_event_or_artifact_chain", "not_locator_count_only"],
        "acceptable_outcomes": ["validated_present", "blocked_unavailable"],
    },
    "structured_state_before_codes": {
        "proof_class": "state_before",
        "must_prove": ["pre_action_state_facts", "evidence_available_before_action", "no_post_action_leak"],
        "acceptable_outcomes": ["validated_present", "validated_absent", "blocked_unavailable"],
    },
    "state_delta_or_state_after_codes": {
        "proof_class": "state_delta",
        "must_prove": ["observation_or_verifier_changes_state", "state_after_differs_or_no_progress", "causal_order"],
        "acceptable_outcomes": ["validated_present", "validated_absent", "blocked_unavailable"],
    },
    "patch_apply_or_no_patch_status": {
        "proof_class": "patch_or_no_patch_status",
        "must_prove": ["patch_applied_failed_or_not_applicable", "no_patch_reason_if_no_patch", "not_inferred_from_task_family"],
        "acceptable_outcomes": ["validated_present", "validated_absent", "not_applicable", "blocked_unavailable"],
    },
    "stop_continue_policy_label": {
        "proof_class": "stop_continue",
        "must_prove": ["completion_gate_or_continuation_reason", "verifier_sufficiency", "not_observed_action_imitation"],
        "acceptable_outcomes": ["validated_present", "validated_absent", "not_applicable", "blocked_unavailable"],
    },
    "independent_policy_label_and_candidate_action_set": {
        "proof_class": "independent_policy_label",
        "must_prove": ["candidate_action_set_available", "chosen_policy_label_independently_reviewed", "hard_negatives_role_distinct"],
        "acceptable_outcomes": ["validated_present", "blocked_unavailable"],
    },
    "external_patch_effect_or_no_patch_reason": {
        "proof_class": "external_patch_effect_or_no_patch_reason",
        "must_prove": ["verifier_relevance", "patch_effect_or_explicit_no_patch", "not_pass_to_pass_repair_claim"],
        "acceptable_outcomes": ["validated_present", "validated_absent", "not_applicable", "blocked_unavailable"],
    },
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "stage12503_return_file_written": False,
    "candidate_return_file_written": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
}
ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "stage12503_return_records_written": 0,
    "candidate_return_records_written": 0,
}

class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12515 raw leak guard rejected {len(issues)} public field(s)")


def work_order(record: dict[str, Any], slot: str) -> dict[str, Any]:
    req = SLOT_REQUIREMENTS[slot]
    item = {
        "record_type": "stage12515_private_causal_evidence_acquisition_work_order_v1",
        "acquisition_work_order_id_hash": stable_hash({"revalidation": record.get("revalidation_id_hash"), "slot": slot}),
        "revalidation_id_hash": record.get("revalidation_id_hash"),
        "request_id_hash": record.get("request_id_hash"),
        "work_item_id_hash": record.get("work_item_id_hash"),
        "packet_id_hash": record.get("packet_id_hash"),
        "root_or_window_hash": record.get("root_or_window_hash"),
        "source_stage": record.get("source_stage"),
        "source_kind": record.get("source_kind"),
        "language_family": record.get("language_family"),
        "task_family": record.get("task_family"),
        "reviewer_group_key_hash": stable_hash({
            "source": record.get("source_stage"),
            "language": record.get("language_family"),
            "task": record.get("task_family"),
        }),
        "stage12514_residual_blocker_codes": sorted(record.get("corrected_residual_blocker_codes") or []),
        "evidence_slot": slot,
        "proof_class": req["proof_class"],
        "must_prove": req["must_prove"],
        "acceptable_return_statuses": req["acceptable_outcomes"],
        "private_reviewer_instruction": "inspect_private_source_only_and_return_hash_status_enum_no_raw_values",
        "hard_reject_if_basis_only": [
            "locator_count",
            "context_locator_ref",
            "stage12509_template",
            "stage12513_status_hash",
            "stage12504_slot_update",
            "observed_action_without_policy_review",
            "local_model_guess",
        ],
        "expected_future_return_target": "stage12503_authoritative_private_semantic_extraction_return_v1_slot_update_candidate",
        "candidate_return_records_written": 0,
        "stage12503_return_records_written": 0,
        "public_safe_status_only": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(item)
    return item


def bundle(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in records:
        groups[(str(item["source_stage"]), str(item["language_family"]), str(item["task_family"]), str(item["evidence_slot"]))].append(item)
    bundles: list[dict[str, Any]] = []
    for (source_stage, language, task, slot), items in sorted(groups.items()):
        row = {
            "record_type": "stage12515_private_causal_evidence_acquisition_bundle_v1",
            "bundle_id_hash": stable_hash({"source": source_stage, "language": language, "task": task, "slot": slot}),
            "source_stage": source_stage,
            "language_family": language,
            "task_family": task,
            "evidence_slot": slot,
            "proof_class": SLOT_REQUIREMENTS[slot]["proof_class"],
            "work_order_count": len(items),
            "request_id_hashes": sorted(item["request_id_hash"] for item in items if item.get("request_id_hash")),
            "next_action": "assign_private_reviewer_or_extractor_for_this_slot_bundle",
            "public_safe_status_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        bundles.append(row)
    return bundles


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    out.mkdir(parents=True, exist_ok=True)
    records = read_jsonl(root / "runs/local/artifacts" / STAGE12514 / "causal_proof_revalidation_records.jsonl")
    work_orders: list[dict[str, Any]] = []
    for record in records:
        for slot in record.get("required_next_private_evidence_slots") or []:
            if slot in SLOT_REQUIREMENTS:
                work_orders.append(work_order(record, slot))
    bundles = bundle(work_orders)
    slot_counts = Counter(row["evidence_slot"] for row in work_orders)
    proof_counts = Counter(row["proof_class"] for row in work_orders)
    lang_counts = Counter(str(row.get("language_family")) for row in work_orders)
    task_counts = Counter(str(row.get("task_family")) for row in work_orders)
    source_counts = Counter(str(row.get("source_stage")) for row in work_orders)
    contract = {
        "record_type": "stage12515_private_causal_evidence_acquisition_contract_v1",
        "stage": STAGE,
        "input_stage": STAGE12514,
        "work_order_scope": "independent_private_causal_evidence_acquisition_only",
        "required_slots": sorted(SLOT_REQUIREMENTS),
        "forbidden_basis_only": ["locator_count", "template", "status_hash", "context_ref", "local_model_guess"],
        "public_artifact_policy": "hashes_enums_status_only_no_raw_paths_commands_diffs_source_or_verifier_output",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12515_private_causal_evidence_acquisition_summary_v1",
        "decision": "private_causal_evidence_acquisition_work_orders_ready_no_training_or_admission",
        "claim_boundary": "Work orders only. No causal proof is claimed, no candidate returns are written, and no training/admission/Level-3/patch trace artifacts are emitted.",
        "input_revalidation_record_count": len(records),
        "acquisition_work_order_count": len(work_orders),
        "source_language_task_bundle_count": len(bundles),
        "bundle_count": len(bundles),
        "evidence_slot_counts": dict(sorted(slot_counts.items())),
        "proof_class_counts": dict(sorted(proof_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_stage_counts": dict(sorted(source_counts.items())),
        "next_stage": "run_private_reviewers_or_extractors_on_stage12515_slot_bundles_then_return_validated_status_only_slot_evidence",
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks({"summary": summary, "contract": contract, "work_orders": work_orders, "bundles": bundles})
    write_jsonl(out / "private_causal_evidence_acquisition_work_orders.jsonl", work_orders)
    write_jsonl(out / "private_causal_evidence_acquisition_bundles.jsonl", bundles)
    write_json(out / "private_causal_evidence_acquisition_contract.json", contract)
    write_json(out / "guardrail_scan.json", {"stage": STAGE, "scan_passed": True, "raw_leak_count": 0, "raw_leak_issue_hashes": []})
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
