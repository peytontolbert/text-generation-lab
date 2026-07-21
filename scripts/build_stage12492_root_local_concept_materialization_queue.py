#!/usr/bin/env python3
"""Root-local materialization queue for reviewed concept proposals.

Stage12492 expands Stage12491 concept materialization requirements into
root-local work items. It does not create training rows. It defines the
minimum concrete fields and quotas needed before Stage12493 can attempt
materialization.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12492_root_local_concept_materialization_queue"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12491 = "stage12491_concept_proposal_semantic_review_gate"
REQUIREMENTS = ROOT / "runs/local/artifacts" / STAGE12491 / "root_local_concept_materialization_requirements.jsonl"
STAGE12491_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12491}.json"

LANGUAGE_FLOORS = ["python", "rust", "c_cpp", "web_js_ts_html"]
ROOTS_PER_REQUIREMENT = 8
ROWS_PER_ROOT_TARGET = 4
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
}

COMMON_REQUIRED_FIELDS = [
    "root_id_hash",
    "source_family_hash",
    "root_lineage_key_hash",
    "language_family",
    "task_family",
    "transition_function_key_hash",
    "state_before_codes",
    "candidate_action_set_hash",
    "independent_policy_label_hash",
    "observation_status_class",
    "state_delta_codes",
    "stop_continue_label_hash",
    "renderer_contract_hash",
    "anti_shortcut_audit_hash",
]

TASK_SPECIFIC_GATES = {
    "transition_continue_or_stop": [
        "must_include_continue_stop_retry_escalate_candidates",
        "must_include_stop_wrong_when_verifier_incomplete_negative",
        "must_include_continue_wrong_when_done_negative",
    ],
    "transition_next_action": [
        "must_include_retrieve_select_test_patch_verify_finish_alternatives",
        "must_not_use_observed_action_as_gold_without_policy_review",
        "must_include_tempting_patch_too_early_negative",
    ],
    "transition_verifier_transition": [
        "must_include_before_after_status_pair",
        "must_distinguish_build_pass_from_build_and_run_pass",
        "must_include_not_exercised_or_insufficient_evidence_negative",
    ],
    "event_local_transition_observation": [
        "must_include_observation_status_class",
        "must_label_event_local_support_not_level3_repair",
        "must_include_state_delta_codes_or_block",
    ],
}


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


def target_row_floor(task_family: str) -> int:
    if task_family == "event_local_transition_observation":
        return 16
    return 32


def queue_item(requirement: dict[str, Any], index: int) -> dict[str, Any]:
    task_family = str(requirement.get("task_family") or "unknown")
    return {
        "record_type": "stage12492_root_local_concept_materialization_work_item_v1",
        "work_item_id_hash": stable_hash({"proposal": requirement.get("proposal_id_hash"), "index": index}),
        "source_proposal_id_hash": requirement.get("proposal_id_hash"),
        "source_proposal_rank": requirement.get("proposal_rank"),
        "concept_variant_family": requirement.get("concept_variant_family"),
        "task_family": task_family,
        "transition_function_key_hash": requirement.get("transition_function_key_hash"),
        "target_language_families": LANGUAGE_FLOORS,
        "target_root_count": ROOTS_PER_REQUIREMENT,
        "target_rows_per_root": ROWS_PER_ROOT_TARGET,
        "target_row_floor": target_row_floor(task_family),
        "required_model_visible_fields": COMMON_REQUIRED_FIELDS,
        "task_specific_gates": TASK_SPECIFIC_GATES.get(task_family, ["task_family_gate_missing_block_before_admission"]),
        "anti_collapse_requirements": [
            "max_duplicate_cluster_share_0_20_for_train_support",
            "max_source_family_share_0_15",
            "candidate_role_entropy_required",
            "option_permutation_required_before_eval",
            "renderer_consistency_required",
            "local_model_label_is_hint_not_gold",
        ],
        "allowed_source_lanes": [
            "stage12295_transition_function_ledger_public_safe",
            "stage12320_event_local_reviewed_support_public_safe",
            "future_root_local_source_adapter",
        ],
        "blocked_until": [
            "root_local_source_records_exist",
            "independent_policy_label_review_passes",
            "state_delta_review_passes",
            "candidate_action_set_materialized",
            "anti_shortcut_audit_passes",
        ],
        "claim_boundary": {
            "materialization_work_item": True,
            "reviewed_train_support": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12491_summary = read_json(STAGE12491_SUMMARY)
    requirements = read_jsonl(REQUIREMENTS)
    work_items = [queue_item(req, i) for i, req in enumerate(requirements, 1)]

    task_counts = Counter(row["task_family"] for row in work_items)
    target_roots = sum(row["target_root_count"] for row in work_items)
    target_rows = sum(row["target_row_floor"] for row in work_items)
    issue_hashes = scan({"work_items": work_items})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12492_root_local_concept_materialization_queue_summary_v1",
        "decision": "root_local_concept_materialization_queue_ready_no_training_no_admission"
        if work_items and guardrail["scan_passed"]
        else "blocked_empty_or_guardrail_failed",
        "source_stage_refs": [STAGE12491],
        "stage12491_materialization_requirement_count": stage12491_summary.get("materialization_requirement_count", len(requirements)),
        "work_item_count": len(work_items),
        "target_root_count_floor": target_roots,
        "target_row_floor": target_rows,
        "target_language_family_count": len(LANGUAGE_FLOORS),
        "task_family_counts": dict(sorted(task_counts.items())),
        "required_model_visible_field_count": len(COMMON_REQUIRED_FIELDS),
        "next_stage": "stage12493_root_local_concept_source_adapter",
        "raw_leak_count": guardrail["raw_leak_count"],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash({"work_items": len(work_items), "target_rows": target_rows}),
    }

    write_jsonl(OUT / "root_local_concept_materialization_work_items.jsonl", work_items)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
