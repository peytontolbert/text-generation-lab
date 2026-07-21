#!/usr/bin/env python3
"""Stage12391 audit-only manual review packet admission gate.

Reads Stage12390 manual review policy candidate packets and emits reviewed
manual packets with fail-closed gate results. This stage does not admit
Level-3, patch-trace, strict/source-heldout, or training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12391_manual_review_packet_admission_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

INPUT = (
    ROOT
    / "runs/local/artifacts/stage12390_patch_attempt_segmenter_and_policy_candidate_builder"
    / "manual_review_policy_candidate_packets.jsonl"
)
INPUT_SUMMARY = ROOT / "runs/summaries/stage12390_patch_attempt_segmenter_and_policy_candidate_builder.json"

SELF_REPO_FAMILIES = {"agentkernel-seq2seq-text-lab"}
GENERIC_REPO_LABELS = {"", "unknown", "missing", "clone", "repo", "src", "worktree"}
FORBIDDEN_ADMISSION_FIELDS = {
    "training_allowed",
    "train_support_allowed",
    "level3_admitted",
    "patch_trace_admitted",
    "strict_eval_eligible",
    "source_heldout_admissible",
    "policy_candidate_set_admitted",
    "new_training_row_emitted",
}
RAW_VISIBILITY_FALSE_FIELDS = {
    "raw_source_path_emitted",
    "raw_cwd_path_emitted",
    "raw_workspace_path_emitted",
    "raw_command_text_emitted",
    "raw_tool_output_emitted",
    "raw_patch_body_emitted",
    "raw_source_text_emitted",
}
RAW_LEAK_PATTERNS = (
    re.compile(r"/(?:data|home|tmp|var|mnt|workspace)/"),
    re.compile(r"\b(?:pytest|python3?|cargo|npm|pnpm|yarn|make|cmake|ctest|node)\s+\S+"),
    re.compile(r"(?m)^\s*(?:diff --git|@@ |\+\+\+ |--- )"),
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def bool_true(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def gate(status: str, passed: bool, blockers: list[str], **extra: Any) -> dict[str, Any]:
    payload = {
        "status": status,
        "passed": passed,
        "blockers": sorted(dict.fromkeys(blockers)),
    }
    payload.update(extra)
    return payload


def review_repo_identity(row: dict[str, Any]) -> dict[str, Any]:
    repo_family = str(row.get("repo_family") or "")
    source_ids = row.get("source_ids") if isinstance(row.get("source_ids"), dict) else {}
    blockers: list[str] = []

    required_ids_present = all(
        bool(source_ids.get(key))
        for key in [
            "source_semantic_review_record_id",
            "source_recovery_record_id",
            "source_stage12316_id",
            "task_window_id",
            "source_file_hash_compat",
        ]
    )
    if not repo_family or repo_family in GENERIC_REPO_LABELS:
        blockers.append("repo_identity_missing_or_generic")
    if not required_ids_present:
        blockers.append("repo_identity_source_lineage_incomplete")
    if "repo_identity_semantic_review_required" in set(row.get("remaining_blockers") or []):
        blockers.append("repo_identity_semantic_review_required")
    if repo_family in SELF_REPO_FAMILIES:
        blockers.append("self_repo_identity_not_scale_diverse")

    if blockers:
        status = "blocked_repo_identity_not_fully_proven"
    else:
        status = "metadata_present_but_manual_identity_proof_required"
        blockers.append("repo_identity_semantic_review_required")

    return gate(
        status,
        False,
        blockers,
        repo_family_candidate=repo_family or None,
        source_lineage_ids_present=required_ids_present,
        self_repo_family=repo_family in SELF_REPO_FAMILIES,
        raw_path_or_source_text_emitted=False,
    )


def review_selected_verifier(row: dict[str, Any]) -> dict[str, Any]:
    selected = (
        row.get("selected_verifier_identity_candidate")
        if isinstance(row.get("selected_verifier_identity_candidate"), dict)
        else {}
    )
    status = str(row.get("verifier_after_patch_status") or "")
    blockers: list[str] = []

    selected_present = selected.get("status") == "selected_for_manual_review"
    verifier_identity_present = bool(selected.get("command_head_hash") and selected.get("command_head_class"))
    if status != "VERIFIER_PASS_OBSERVED":
        blockers.append("selected_verifier_after_patch_not_pass")
    if not selected_present:
        blockers.append("selected_verifier_missing")
    if not verifier_identity_present:
        blockers.append("selected_verifier_identity_incomplete")
    if "verifier_relevance_semantic_review_required" in set(row.get("remaining_blockers") or []):
        blockers.append("verifier_relevance_semantic_review_required")
    blockers.append("selected_verifier_relevance_not_semantically_proven")

    return gate(
        "blocked_selected_verifier_relevance_not_fully_proven",
        False,
        blockers,
        verifier_after_patch_status=status or None,
        selected_verifier_present=selected_present,
        selected_verifier_identity_present=verifier_identity_present,
        command_head_class=selected.get("command_head_class"),
        raw_command_text_emitted=False,
        raw_tool_output_emitted=False,
    )


def review_policy_label(row: dict[str, Any]) -> dict[str, Any]:
    proposal = (
        row.get("policy_candidate_set_proposal")
        if isinstance(row.get("policy_candidate_set_proposal"), dict)
        else {}
    )
    labels = proposal.get("opaque_labels") if isinstance(proposal.get("opaque_labels"), list) else []
    blockers: list[str] = []

    selected_policy_label = proposal.get("selected_policy_label")
    if not selected_policy_label:
        blockers.append("policy_label_not_selected")
    if not proposal.get("policy_gold_admitted"):
        blockers.append("policy_gold_not_admitted")
    if proposal.get("observed_action_order_only"):
        blockers.append("observed_action_order_only_not_policy_gold")
    if "policy_label_not_admitted" in set(row.get("remaining_blockers") or []):
        blockers.append("policy_label_not_admitted")
    if not labels:
        blockers.append("policy_candidate_options_missing")

    return gate(
        "blocked_policy_label_not_fully_proven",
        False,
        blockers,
        selected_policy_label=selected_policy_label,
        policy_gold_admitted=False,
        opaque_option_count=len(labels),
        raw_command_text_emitted=False,
        raw_tool_output_emitted=False,
        raw_patch_body_emitted=False,
    )


def review_state_delta(row: dict[str, Any]) -> dict[str, Any]:
    segmentation = row.get("segmentation") if isinstance(row.get("segmentation"), dict) else {}
    blockers: list[str] = []
    patch_applied = row.get("patch_apply_status") == "PATCH_APPLIED"
    atomic = bool(segmentation.get("atomic_patch_attempt_candidate"))

    if not patch_applied:
        blockers.append("patch_not_applied")
    if not atomic:
        blockers.append("patch_attempt_not_atomic")
    if "state_delta_semantic_review_required" in set(row.get("remaining_blockers") or []):
        blockers.append("state_delta_semantic_review_required")
    blockers.append("state_delta_semantics_not_proven_from_packet")

    return gate(
        "blocked_state_delta_not_fully_proven",
        False,
        blockers,
        patch_apply_status=row.get("patch_apply_status"),
        atomic_patch_attempt_candidate=atomic,
        state_delta_semantics_proven=False,
        raw_patch_body_emitted=False,
        raw_source_text_emitted=False,
    )


def review_source_diversity(row: dict[str, Any], global_repo_counts: Counter[str], unique_source_hashes: int) -> dict[str, Any]:
    repo_family = str(row.get("repo_family") or "missing")
    blockers: list[str] = []
    if repo_family in SELF_REPO_FAMILIES:
        blockers.append("self_repo_dominated_scale_claim_blocked")
    if len(global_repo_counts) < 2:
        blockers.append("single_repo_family_manual_packet_set")
    if unique_source_hashes < 2:
        blockers.append("insufficient_distinct_source_hashes")
    blockers.append("source_diversity_not_sufficient_for_admission_claim")

    return gate(
        "blocked_source_diversity_not_admission_grade",
        False,
        blockers,
        repo_family=repo_family,
        repo_family_packet_count=global_repo_counts.get(repo_family, 0),
        unique_repo_families=len(global_repo_counts),
        unique_source_hashes=unique_source_hashes,
        source_diversity_claim_allowed=False,
    )


def iter_string_paths(value: Any, path: str = "$") -> list[tuple[str, str]]:
    if isinstance(value, dict):
        out: list[tuple[str, str]] = []
        for key, item in value.items():
            out.extend(iter_string_paths(item, f"{path}.{key}"))
        return out
    if isinstance(value, list):
        out = []
        for index, item in enumerate(value):
            out.extend(iter_string_paths(item, f"{path}[{index}]"))
        return out
    if isinstance(value, str):
        return [(path, value)]
    return []


def raw_leak_findings(row: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    raw_visibility = row.get("raw_visibility") if isinstance(row.get("raw_visibility"), dict) else {}
    for field in RAW_VISIBILITY_FALSE_FIELDS:
        if bool_true(raw_visibility.get(field)):
            findings.append(f"{field}_true")
    for path, text in iter_string_paths(row):
        if path.endswith("source_ids.source_file_hash_compat"):
            continue
        for pattern in RAW_LEAK_PATTERNS:
            if pattern.search(text):
                findings.append(f"raw_like_string_at_{path}")
                break
    return sorted(dict.fromkeys(findings))


def admission_findings(row: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if bool_true(row.get("training_allowed")):
        findings.append("row_training_allowed_true")
    admission = row.get("admission") if isinstance(row.get("admission"), dict) else {}
    for field in FORBIDDEN_ADMISSION_FIELDS:
        if bool_true(admission.get(field)):
            findings.append(f"admission_{field}_true")
    return sorted(findings)


def review_raw_leak_and_admission(row: dict[str, Any]) -> dict[str, Any]:
    leak_findings = raw_leak_findings(row)
    admit_findings = admission_findings(row)
    blockers: list[str] = []
    if leak_findings:
        blockers.append("raw_leak_detected")
    if admit_findings:
        blockers.append("forbidden_admission_flag_detected")
    blockers.extend(
        [
            "level3_admission_requires_separate_full_proof",
            "patch_trace_admission_requires_separate_full_proof",
            "strict_or_source_heldout_admission_requires_separate_full_proof",
            "training_admission_blocked",
        ]
    )

    return gate(
        "raw_leak_absent_but_admission_blocked",
        False,
        blockers,
        raw_leak_check_passed=not leak_findings,
        admission_check_passed=False,
        raw_leak_detected=bool(leak_findings),
        raw_leak_findings=leak_findings,
        forbidden_admission_flag_detected=bool(admit_findings),
        admission_findings=admit_findings,
        training_allowed=False,
        level3_admitted=False,
        patch_trace_admitted=False,
        strict_eval_eligible=False,
        source_heldout_admissible=False,
    )


def review_row(
    row: dict[str, Any],
    global_repo_counts: Counter[str],
    unique_source_hashes: int,
) -> dict[str, Any]:
    source_stage = str(row.get("stage") or "stage12390_patch_attempt_segmenter_and_policy_candidate_builder")
    gate_results = {
        "repo_identity": review_repo_identity(row),
        "selected_verifier_relevance": review_selected_verifier(row),
        "policy_label": review_policy_label(row),
        "state_delta": review_state_delta(row),
        "source_diversity": review_source_diversity(row, global_repo_counts, unique_source_hashes),
        "raw_leak_and_admission": review_raw_leak_and_admission(row),
    }
    remaining = set(row.get("remaining_blockers") or [])
    for result in gate_results.values():
        remaining.update(result["blockers"])
    remaining.update(
        {
            "manual_review_required",
            "training_admission_blocked",
            "level3_control_contract_missing",
            "patch_trace_admission_blocked",
            "strict_eval_admission_blocked",
            "source_heldout_admission_blocked",
        }
    )
    admission = {
        "training_allowed": False,
        "train_support_allowed": False,
        "level3_admitted": False,
        "patch_trace_admitted": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "policy_candidate_set_admitted": False,
        "new_training_row_emitted": False,
        "admitted_for_stage12391": False,
    }

    reviewed = dict(row)
    reviewed.update(
        {
            "stage": STAGE,
            "source_stage": source_stage,
            "record_type": "manual_review_policy_candidate_packet_admission_audit_record",
            "admission_audit_record_id": stable_id(
                "stage12391_admission_audit",
                row.get("patch_attempt_candidate_id"),
                row.get("source_ids"),
            ),
            "gate_results": gate_results,
            "gate_pass_counts": {
                "passed": sum(1 for result in gate_results.values() if result["passed"]),
                "failed_or_blocked": sum(1 for result in gate_results.values() if not result["passed"]),
            },
            "admission_decision": "not_admitted_audit_only_manual_review_still_blocked",
            "remaining_blockers": sorted(remaining),
            "review_required": True,
            "training_allowed": False,
            "admission": admission,
            "raw_visibility": {
                "raw_source_path_emitted": False,
                "raw_cwd_path_emitted": False,
                "raw_workspace_path_emitted": False,
                "raw_command_text_emitted": False,
                "raw_tool_output_emitted": False,
                "raw_patch_body_emitted": False,
                "raw_source_text_emitted": False,
            },
        }
    )
    return reviewed


def next_blocker(blocker_counts: Counter[str]) -> dict[str, Any]:
    priority = [
        "policy_label_not_selected",
        "policy_label_not_admitted",
        "policy_gold_not_admitted",
        "selected_verifier_relevance_not_semantically_proven",
        "state_delta_semantics_not_proven_from_packet",
        "repo_identity_semantic_review_required",
        "self_repo_dominated_scale_claim_blocked",
        "source_diversity_not_sufficient_for_admission_claim",
    ]
    for blocker in priority:
        if blocker_counts.get(blocker):
            return {
                "blocker": blocker,
                "count": blocker_counts[blocker],
                "required_action": "manual_semantic_review_or_new_non_self_source_packet_before_any_admission",
            }
    if blocker_counts:
        blocker, count = blocker_counts.most_common(1)[0]
        return {
            "blocker": blocker,
            "count": count,
            "required_action": "resolve_highest_count_blocker_before_any_admission",
        }
    return {
        "blocker": None,
        "count": 0,
        "required_action": "none",
    }


def write_markdown(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage12391 Manual Review Packet Admission Audit",
        "",
        "Audit-only gate results for Stage12390 manual review policy candidate packets.",
        "",
        f"Packets reviewed: `{summary['manual_packets_reviewed']}`",
        f"Training allowed: `{summary['training_allowed']}`",
        f"Admitted rows: `{summary['admitted_rows']}`",
        f"Next blocker: `{summary['next_blocker']['blocker']}` ({summary['next_blocker']['count']})",
        "",
        "No Level-3, patch-trace, strict-eval, source-heldout, or training admission is emitted.",
    ]
    (OUT / "MANUAL_REVIEW_PACKET_ADMISSION_AUDIT_STAGE12391.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    source_rows = read_jsonl(INPUT)
    source_summary = read_json(INPUT_SUMMARY)
    repo_counts = Counter(str(row.get("repo_family") or "missing") for row in source_rows)
    unique_source_hashes = len(
        {
            (row.get("source_ids") or {}).get("source_file_hash_compat")
            for row in source_rows
            if isinstance(row.get("source_ids"), dict)
            and (row.get("source_ids") or {}).get("source_file_hash_compat")
        }
    )
    reviewed = [review_row(row, repo_counts, unique_source_hashes) for row in source_rows]

    gate_status_counts: dict[str, dict[str, int]] = {}
    gate_pass_counts: dict[str, dict[str, int]] = {}
    blocker_counts: Counter[str] = Counter()
    for row in reviewed:
        blocker_counts.update(row["remaining_blockers"])
        for gate_name, result in row["gate_results"].items():
            gate_status_counts.setdefault(gate_name, {})
            gate_status_counts[gate_name][result["status"]] = gate_status_counts[gate_name].get(result["status"], 0) + 1
            gate_pass_counts.setdefault(gate_name, {"passed": 0, "failed_or_blocked": 0})
            gate_pass_counts[gate_name]["passed" if result["passed"] else "failed_or_blocked"] += 1

    admitted_rows = [
        row
        for row in reviewed
        if all(result["passed"] for result in row["gate_results"].values())
        and row["gate_results"]["repo_identity"]["passed"]
        and row["gate_results"]["selected_verifier_relevance"]["passed"]
        and row["gate_results"]["policy_label"]["passed"]
        and row["gate_results"]["state_delta"]["passed"]
        and row["gate_results"]["source_diversity"]["passed"]
    ]
    blocked_rows = [row for row in reviewed if row not in admitted_rows]
    raw_leak_rows = [
        row["patch_attempt_candidate_id"]
        for row in reviewed
        if row["gate_results"]["raw_leak_and_admission"]["raw_leak_detected"]
        or row["gate_results"]["raw_leak_and_admission"]["forbidden_admission_flag_detected"]
    ]

    summary = {
        "stage": STAGE,
        "decision": "audit_only_manual_review_packet_admission_blocked_no_training",
        "claim_boundary": (
            "Admission audit over Stage12390 manual review packets only. Gate results are emitted for "
            "repo identity, selected verifier relevance, policy label, state delta, source diversity, "
            "and raw leak/admission. No training rows or higher-trust admissions are emitted."
        ),
        "source_stage": source_summary.get("stage") or "stage12390_patch_attempt_segmenter_and_policy_candidate_builder",
        "source_input": str(INPUT.relative_to(ROOT)),
        "manual_packets_reviewed": len(reviewed),
        "training_allowed": False,
        "new_training_rows_emitted": 0,
        "admitted_rows": len(admitted_rows),
        "blocked_rows": len(blocked_rows),
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_eligible": 0,
        "source_heldout_admissible": 0,
        "policy_candidate_set_admitted": 0,
        "repo_family_counts": dict(repo_counts),
        "unique_repo_families": len(repo_counts),
        "unique_source_hashes": unique_source_hashes,
        "source_semantic_review_records": len(
            {
                (row.get("source_ids") or {}).get("source_semantic_review_record_id")
                for row in source_rows
                if isinstance(row.get("source_ids"), dict)
                and (row.get("source_ids") or {}).get("source_semantic_review_record_id")
            }
        ),
        "patch_apply_status_counts": dict(Counter(str(row.get("patch_apply_status")) for row in source_rows)),
        "verifier_after_patch_status_counts": dict(
            Counter(str(row.get("verifier_after_patch_status")) for row in source_rows)
        ),
        "selected_verifier_command_class_counts": dict(
            Counter(
                str((row.get("selected_verifier_identity_candidate") or {}).get("command_head_class") or "missing")
                for row in source_rows
                if isinstance(row.get("selected_verifier_identity_candidate"), dict)
                or row.get("selected_verifier_identity_candidate") is None
            )
        ),
        "gate_status_counts": gate_status_counts,
        "gate_pass_counts": gate_pass_counts,
        "remaining_blocker_counts": dict(blocker_counts),
        "raw_leak_or_forbidden_admission_rows": len(raw_leak_rows),
        "raw_leak_or_forbidden_admission_row_ids": raw_leak_rows[:20],
        "global_admission_boundary": {
            "training_allowed": False,
            "per_row_training_allowed_required": False,
            "emit_training_rows": False,
            "level3_admission_allowed": False,
            "patch_trace_admission_allowed": False,
            "strict_eval_admission_allowed": False,
            "source_heldout_admission_allowed": False,
            "raw_source_path_emission_allowed": False,
            "raw_command_emission_allowed": False,
            "raw_output_emission_allowed": False,
            "raw_patch_body_emission_allowed": False,
        },
        "next_blocker": next_blocker(blocker_counts),
        "next_stage": {
            "training_allowed": False,
            "auto_admission_allowed": False,
            "required_before_any_admission": [
                "manual_policy_label_selection_with_gold_justification",
                "manual_selected_verifier_relevance_proof",
                "manual_state_delta_semantic_proof",
                "manual_repo_identity_proof",
                "non_self_or_diverse_source_support_before_scale_claim",
                "separate_full_proof_before_level3_patch_trace_strict_or_source_heldout_admission",
            ],
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "reviewed_manual_policy_candidate_packets.jsonl", reviewed)
    write_jsonl(OUT / "blocked_manual_policy_candidate_packets.jsonl", blocked_rows)
    write_jsonl(OUT / "admitted_manual_policy_candidate_packets_should_be_empty.jsonl", admitted_rows)
    write_json(OUT / "manual_review_packet_admission_audit_summary.json", summary)
    write_markdown(summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
