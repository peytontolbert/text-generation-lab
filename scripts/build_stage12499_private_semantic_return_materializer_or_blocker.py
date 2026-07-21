#!/usr/bin/env python3
"""Stage12496 return production materializer or blocker audit.

Stage12499 consumes Stage12498 eligible slots and Stage12495 work items. It may
only write Stage12496 returns when independent private semantic review proofs
already exist. In the current public-safe artifacts those proofs are absent, so
the stage emits a concrete per-slot blocker audit and creates no return file.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12499_private_semantic_return_materializer_or_blocker"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12495 = "stage12495_independent_policy_label_and_action_set_review"
STAGE12498 = "stage12498_review_return_template_work_order"

WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12495 / "independent_policy_label_review_work_items.jsonl"
WORK_ORDER_SLOTS = ROOT / "runs/local/artifacts" / STAGE12498 / "review_return_work_order_slots.jsonl"
EVENT_LOCAL_REFS = ROOT / "runs/local/artifacts" / STAGE12498 / "event_local_non_promotion_refs.jsonl"
STAGE12495_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12495}.json"
STAGE12498_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12498}.json"
RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12495 / "independent_policy_label_review_returns.jsonl"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
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
}

ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "independent_policy_labels_validated": 0,
    "independent_policy_labels_admitted": 0,
    "stage12496_return_records_written": 0,
}

IDENTITY_FIELDS = [
    "review_item_id_hash",
    "packet_id_hash",
    "source_candidate_id_hash",
    "work_item_id_hash",
    "task_family",
    "language_family",
    "candidate_option_set_hash",
]

PRIVATE_PROOF_FIELDS = [
    "reviewer_id_hash",
    "reviewer_conflict_check_hash",
    "candidate_action_set_rewritten_hash",
    "candidate_action_set_rewrite_rationale_hash",
    "independent_policy_label_hash",
    "independent_policy_label_rationale_hash",
    "state_before_semantic_review_hash",
    "state_delta_semantic_review_hash",
    "hard_negative_audit_hash",
    "anti_shortcut_audit_hash",
    "option_permutation_audit_hash",
    "deterministic_blinded_shuffle_hash",
]

PRIVATE_PROOF_REQUIREMENTS = [
    "independent_private_semantic_reviewer_identity",
    "independent_reviewer_conflict_check",
    "candidate_action_set_rewrite_with_at_least_six_action_families",
    "candidate_action_set_rewrite_rationale",
    "independent_policy_label_selection",
    "independent_policy_label_rationale",
    "state_before_semantic_review",
    "state_delta_semantic_review",
    "hard_negative_audit_with_at_least_two_negatives",
    "anti_shortcut_audit",
    "option_permutation_audit",
    "deterministic_blinded_shuffle_proof",
]

BLOCKER_CODES = [
    "private_semantic_review_packet_absent",
    "independent_policy_label_hash_missing",
    "candidate_action_set_rewritten_hash_missing",
    "state_before_semantic_review_hash_missing",
    "state_delta_semantic_review_hash_missing",
    "hard_negative_audit_hash_missing",
    "anti_shortcut_audit_hash_missing",
    "option_permutation_audit_hash_missing",
    "deterministic_blinded_shuffle_hash_missing",
    "honest_stage12496_return_would_require_fabrication",
]


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
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


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def slot_blocker(slot: dict[str, Any], work_item: dict[str, Any] | None) -> dict[str, Any]:
    identity_mismatches = [
        field
        for field in IDENTITY_FIELDS
        if work_item is None or slot.get(field) != work_item.get(field)
    ]
    missing_stage12495_blockers = list(work_item.get("blocker_codes", [])) if work_item else ["stage12495_work_item_missing"]
    return {
        "record_type": "stage12499_return_production_blocker_slot_v1",
        "blocker_slot_id_hash": stable_hash({"slot": slot.get("slot_id_hash"), "review": slot.get("review_item_id_hash")}),
        "source_slot_id_hash": slot.get("slot_id_hash"),
        "review_item_id_hash": slot.get("review_item_id_hash"),
        "packet_id_hash": slot.get("packet_id_hash"),
        "source_candidate_id_hash": slot.get("source_candidate_id_hash"),
        "work_item_id_hash": slot.get("work_item_id_hash"),
        "task_family": slot.get("task_family"),
        "language_family": slot.get("language_family"),
        "candidate_option_set_hash": slot.get("candidate_option_set_hash"),
        "return_eligible_for_stage12496": bool(slot.get("return_eligible_for_stage12496")),
        "return_created": False,
        "can_honestly_materialize_return": False,
        "blocker_codes": BLOCKER_CODES,
        "missing_private_proof_fields": PRIVATE_PROOF_FIELDS,
        "missing_private_proof_requirements": PRIVATE_PROOF_REQUIREMENTS,
        "stage12495_unresolved_blockers": missing_stage12495_blockers,
        "identity_field_mismatch_count": len(identity_mismatches),
        "identity_field_mismatches": identity_mismatches,
        "fabrication_risk_fields": [
            "independent_policy_label_hash",
            "candidate_action_set_rewritten_hash",
            "state_before_semantic_review_hash",
            "state_delta_semantic_review_hash",
            "hard_negative_audit_hash",
            "anti_shortcut_audit_hash",
            "option_permutation_audit_hash",
            "deterministic_blinded_shuffle_hash",
        ],
        "forbidden_derivation_sources": [
            "observed_action",
            "event_order",
            "local_model_proposal",
            "prior_target_value",
        ],
        "public_safe_status_only": True,
        "raw_private_values_revealed": False,
        "observed_action_available_to_labeler": False,
        "observed_action_used_as_label": False,
        "local_model_authority": False,
        "event_local_promoted": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def shard_manifests(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in blockers:
        grouped[(str(row.get("task_family")), str(row.get("language_family")))].append(row)

    manifests: list[dict[str, Any]] = []
    for (task_family, language_family), rows in sorted(grouped.items()):
        manifests.append(
            {
                "record_type": "stage12499_return_production_blocker_shard_manifest_v1",
                "shard_id_hash": stable_hash({"task": task_family, "language": language_family}),
                "task_family": task_family,
                "language_family": language_family,
                "slot_count": len(rows),
                "review_item_id_hashes": sorted(row["review_item_id_hash"] for row in rows),
                "return_records_written": 0,
                "can_honestly_materialize_returns": False,
                "shared_blocker_codes": BLOCKER_CODES,
                "missing_private_proof_fields": PRIVATE_PROOF_FIELDS,
                "public_safe_status_only": True,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    return manifests


def event_local_exclusion(ref: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12499_event_local_exclusion_preserved_v1",
        "event_local_ref_hash": ref.get("event_local_ref_hash"),
        "review_item_id_hash": ref.get("review_item_id_hash"),
        "packet_id_hash": ref.get("packet_id_hash"),
        "task_family": ref.get("task_family"),
        "language_family": ref.get("language_family"),
        "return_eligible_for_stage12496": False,
        "event_local_promoted": False,
        "reason_codes": ref.get("reason_codes", []),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12495_summary = read_json(STAGE12495_SUMMARY)
    stage12498_summary = read_json(STAGE12498_SUMMARY)
    work_items = read_jsonl(WORK_ITEMS)
    slots = read_jsonl(WORK_ORDER_SLOTS)
    event_refs = read_jsonl(EVENT_LOCAL_REFS)
    work_by_review_id = {row.get("review_item_id_hash"): row for row in work_items}

    blockers = [slot_blocker(slot, work_by_review_id.get(slot.get("review_item_id_hash"))) for slot in slots]
    shards = shard_manifests(blockers)
    event_local_exclusions = [event_local_exclusion(ref) for ref in event_refs]

    language_counts = Counter(row["language_family"] for row in blockers)
    task_counts = Counter(row["task_family"] for row in blockers)
    blocker_counts: Counter[str] = Counter()
    for row in blockers:
        blocker_counts.update(row["blocker_codes"])

    issue_hashes = scan(
        {
            "blockers": blockers,
            "shards": shards,
            "event_local_exclusions": event_local_exclusions,
        }
    )
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }

    return_file_preexisting = RETURN_FILE.exists()
    summary = {
        "stage": STAGE,
        "record_type": "stage12499_private_semantic_return_materializer_or_blocker_summary_v1",
        "decision": "blocked_honest_stage12496_return_materialization_missing_private_semantic_proofs",
        "source_stage_refs": [STAGE12495, STAGE12498],
        "stage12495_decision": stage12495_summary.get("decision"),
        "stage12498_decision": stage12498_summary.get("decision"),
        "input_work_item_count": len(work_items),
        "stage12498_slot_count": len(slots),
        "eligible_slot_count": len(blockers),
        "blocked_slot_count": len(blockers),
        "return_file_preexisting": return_file_preexisting,
        "return_file_created_by_stage": False,
        "return_records_written": 0,
        "stage12496_return_records_written": 0,
        "stage12496_validatable_return_count": 0,
        "independent_semantic_label_materialized_count": 0,
        "candidate_action_set_rewrite_materialized_count": 0,
        "state_before_review_materialized_count": 0,
        "state_delta_review_materialized_count": 0,
        "hard_negative_audit_materialized_count": 0,
        "anti_shortcut_audit_materialized_count": 0,
        "option_permutation_audit_materialized_count": 0,
        "blinded_shuffle_materialized_count": 0,
        "fabrication_prevented_count": len(blockers),
        "missing_private_proof_field_count_per_slot": len(PRIVATE_PROOF_FIELDS),
        "shard_manifest_count": len(shards),
        "event_local_input_count": len(event_refs),
        "event_local_excluded_count": len(event_local_exclusions),
        "event_local_promoted_count": 0,
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "private_semantic_review_proof_acquisition_before_stage12496_returns",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "blocked": len(blockers),
                "event_local": len(event_local_exclusions),
                "shards": len(shards),
                "blockers": dict(blocker_counts),
            }
        ),
    }

    write_jsonl(OUT / "return_production_blocker_slots.jsonl", blockers)
    write_jsonl(OUT / "return_production_blocker_shard_manifests.jsonl", shards)
    write_jsonl(OUT / "event_local_exclusion_preserved.jsonl", event_local_exclusions)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
