#!/usr/bin/env python3
"""Semantic review gate for Stage12490 concept proposals.

Stage12491 reviews proposal-only concepts and decides whether they can become
train-support rows. It intentionally fails closed for aggregate metadata
proposals that lack root-local state, independent policy labels, state deltas,
and candidate action sets. Blocked proposals are converted into concrete
materialization requirements for a later stage.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12491_concept_proposal_semantic_review_gate"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12490 = "stage12490_local_model_concept_proposal_queue"
PROPOSALS = ROOT / "runs/local/artifacts" / STAGE12490 / "local_model_concept_proposal_queue.jsonl"
STAGE12490_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12490}.json"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

REQUIRED_TRAIN_SUPPORT_FIELDS = [
    "root_id_hash",
    "source_family_hash",
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


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


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


def review_proposal(row: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    reasons: list[str] = []
    if row.get("eligible_for_stage12491_review") is not True:
        reasons.append("not_stage12491_review_eligible")
    if row.get("eligible_for_training_or_admission") is not False:
        reasons.append("proposal_already_claims_training_or_admission")
    if row.get("training_allowed") is not False or row.get("admission_allowed") is not False:
        reasons.append("proposal_training_or_admission_flag_not_false")
    if row.get("external_repair_credit_count") != 0:
        reasons.append("proposal_claims_external_repair_credit")
    blockers = row.get("anti_collapse_train_support_blockers")
    if blockers:
        reasons.append("anti_collapse_blockers_present")
    if row.get("language_family") == "mixed_or_unknown_public_metadata":
        reasons.append("language_family_not_root_specific")
    if row.get("concept_variant_family") == "proof_boundary_gap_concept_noncredit":
        reasons.append("proof_boundary_concept_never_train_support")
    if not row.get("candidate_action_set_hash"):
        reasons.append("candidate_action_set_not_materialized")
    if not row.get("root_lineage_key_hash"):
        reasons.append("root_lineage_not_materialized")
    if not row.get("state_code_candidate_hash"):
        reasons.append("state_codes_not_materialized")

    materialization = {
        "record_type": "stage12491_concept_materialization_requirement_v1",
        "proposal_id_hash": row.get("proposal_id_hash"),
        "proposal_rank": row.get("proposal_rank"),
        "concept_variant_family": row.get("concept_variant_family"),
        "task_family": row.get("task_family"),
        "transition_function_key_hash": row.get("transition_function_key_hash"),
        "required_train_support_fields": REQUIRED_TRAIN_SUPPORT_FIELDS,
        "must_generate_root_local_candidates": True,
        "must_have_independent_policy_label": True,
        "must_have_state_delta_review": True,
        "must_have_renderer_consistency_review": True,
        "must_not_use_local_model_label_as_gold": True,
        "must_not_claim_proof_grade_repair": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    return reasons, materialization


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12490_summary = read_json(STAGE12490_SUMMARY)
    proposals = read_jsonl(PROPOSALS)

    accepted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    materialization: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()

    for row in proposals:
        reasons, req = review_proposal(row)
        if reasons:
            reason_counts.update(reasons)
            blocked.append(
                {
                    "record_type": "stage12491_blocked_concept_proposal_ref_v1",
                    "proposal_id_hash": row.get("proposal_id_hash"),
                    "proposal_rank": row.get("proposal_rank"),
                    "concept_variant_family": row.get("concept_variant_family"),
                    "task_family": row.get("task_family"),
                    "reason_codes": sorted(set(reasons)),
                    **FALSE_GUARDS,
                    **ZERO_GUARDS,
                }
            )
            if row.get("eligible_for_stage12491_review") is True and row.get("concept_variant_family") != "proof_boundary_gap_concept_noncredit":
                materialization.append(req)
        else:
            accepted.append(
                {
                    "record_type": "stage12491_reviewed_concept_train_support_candidate_ref_v1",
                    "proposal_id_hash": row.get("proposal_id_hash"),
                    "proposal_rank": row.get("proposal_rank"),
                    "review_status": "accepted_for_future_train_support_packaging",
                    **FALSE_GUARDS,
                    **ZERO_GUARDS,
                }
            )

    guardrail_payload = {"accepted": accepted, "blocked": blocked, "materialization": materialization}
    issue_hashes = scan(guardrail_payload)
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }

    decision = (
        "review_gate_complete_materialization_required_no_train_support_admitted"
        if not accepted and materialization and guardrail["scan_passed"]
        else "review_gate_complete_reviewed_train_support_candidates_present_no_packaging"
        if accepted and guardrail["scan_passed"]
        else "blocked_guardrail_or_empty_review"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12491_concept_proposal_semantic_review_gate_summary_v1",
        "decision": decision,
        "source_stage_refs": [STAGE12490],
        "stage12490_proposal_queue_rows": len(proposals),
        "stage12490_eligible_review_rows": stage12490_summary.get("eligible_for_stage12491_review_rows", 0),
        "reviewed_proposal_count": len(proposals),
        "accepted_train_support_candidate_count": len(accepted),
        "blocked_proposal_count": len(blocked),
        "materialization_requirement_count": len(materialization),
        "reason_counts": dict(sorted(reason_counts.items())),
        "required_train_support_field_count": len(REQUIRED_TRAIN_SUPPORT_FIELDS),
        "next_stage": "stage12492_root_local_concept_materialization_queue",
        "raw_leak_count": guardrail["raw_leak_count"],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash({"decision": decision, "accepted": len(accepted), "materialization": len(materialization)}),
    }
    write_jsonl(OUT / "reviewed_concept_train_support_candidates.jsonl", accepted)
    write_jsonl(OUT / "blocked_concept_proposal_refs.jsonl", blocked)
    write_jsonl(OUT / "root_local_concept_materialization_requirements.jsonl", materialization)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
