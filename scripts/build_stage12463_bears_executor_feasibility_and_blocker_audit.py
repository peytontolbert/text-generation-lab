#!/usr/bin/env python3
"""Build Stage12463 fail-closed Bears executor feasibility/blocker audit.

This stage audits whether Stage12462 Bears private proof-slot work orders can be
executed now from already-materialized local/source/verifier evidence. It does
not checkout repositories, run tests, use network, train, package, admit rows,
or inspect raw source material.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12463_bears_executor_feasibility_and_blocker_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"
AUDIT_OUT = OUT_DIR / "feasibility_and_blocker_audit.json"

STAGE12462 = "stage12462_bears_private_proof_slot_executor_work_order"
STAGE12462_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12462}.json"
STAGE12462_ITEMS = (
    ROOT / "runs/local/artifacts" / STAGE12462 / "executor_work_items.jsonl"
)
STAGE12327_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "bears_failing_passing_candidates.jsonl"
)
STAGE12333_HYDRATION_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12333_bears_hydration_request"
    / "bears_hydration_request_summary.json"
)
STAGE12336_BLOCKER_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12336_bears_local_hydration_blocker_audit"
    / "bears_local_hydration_blocker_audit.json"
)

BLOCKER_KEYS = [
    "missing_checkout",
    "missing_submodule_or_git",
    "missing_verifier_command_output",
    "missing_patch_lineage",
    "missing_same_source_causality",
    "java_only_not_multilingual",
]
EXPECTED_GAP = 15
SAFE_EXPECTED_RETURN_PREFIX = "runs/local/artifacts/"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|terminal output|command output|git clone|"
    r"git apply|pytest\s|python -c|bash -|sh -|curl\s)\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "repo",
    "repo_family",
    "repo_id",
    "repo_name",
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "commands",
    "stdout",
    "stderr",
    "diff",
    "patch",
    "patch_body",
    "raw_text",
    "source",
    "source_text",
    "file_content",
    "content",
}
KEY_ALLOW_RE = re.compile(
    r"(hash|hashes|ref|refs|schema|return|expected_return_path|slot|slots|"
    r"blocker|scan|policy)",
    re.IGNORECASE,
)


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


def read_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_no} must contain a JSON object")
            rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 4:
        return "2-4"
    if count <= 9:
        return "5-9"
    if count <= 24:
        return "10-24"
    if count <= 74:
        return "25-74"
    return "75-plus"


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if label.endswith(".expected_return_path") and value.startswith(SAFE_EXPECTED_RETURN_PREFIX):
            return issues
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def validate_stage12462(summary: dict[str, Any], work_items: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if summary.get("stage") != STAGE12462:
        blockers.append("stage12462_unexpected_stage")
    if summary.get("request_count") != len(work_items):
        blockers.append("stage12462_request_count_mismatch")
    if summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12462_guardrail_not_passed")
    for key in [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
    ]:
        if summary.get(key) is not False:
            blockers.append(f"stage12462_{key}_not_false")
    if summary.get("expected_credit_now") not in (0, None):
        blockers.append("stage12462_expected_credit_now_not_zero")
    return blockers


def candidate_support_by_hash(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    support: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_hash = stable_hash(
            {
                "candidate_id": row.get("candidate_id"),
                "patch_diff_hash": row.get("patch_diff_hash"),
                "selected_test_hashes": row.get("selected_test_hashes") or [],
            }
        )
        support[candidate_hash] = {
            "record_ref": candidate_hash,
            "language_family": row.get("language_family"),
            "blocked_reasons": list(row.get("blocked_reasons") or []),
            "raw_policy_hash": stable_hash(row.get("raw_content_policy") or {}),
        }
    return support


def hydration_proves_local_source(
    hydration_summary: dict[str, Any], blocker_audit: dict[str, Any]
) -> bool:
    if not hydration_summary:
        return False
    if blocker_audit.get("decision") == "bears_local_hydration_blocked_fail_closed":
        return False
    probe_results = blocker_audit.get("probe_results") or {}
    if probe_results.get("bears_dot_git_exists") is False:
        return False
    blocked_reasons = set(blocker_audit.get("blocked_reasons") or [])
    if {
        "bears_submodule_uninitialized_no_local_git",
        "bears_git_commands_fall_back_to_parent_repo",
    } & blocked_reasons:
        return False
    return hydration_summary.get("training_allowed") is False


def build_blocker_counts(
    work_items: list[dict[str, Any]],
    stage12462_blockers: list[str],
    hydration_summary: dict[str, Any],
    blocker_audit: dict[str, Any],
) -> dict[str, int]:
    request_count = len(work_items)
    local_source_proven = hydration_proves_local_source(hydration_summary, blocker_audit)
    required_slots = {
        slot
        for item in work_items
        for slot in item.get("required_return_slots", [])
        if isinstance(slot, str)
    }
    blocker_reasons = set(blocker_audit.get("blocked_reasons") or [])
    submodule_blocked = bool(
        {
            "bears_submodule_uninitialized_no_local_git",
            "bears_git_commands_fall_back_to_parent_repo",
        }
        & blocker_reasons
    )

    counts = {key: 0 for key in BLOCKER_KEYS}
    if stage12462_blockers or not local_source_proven:
        counts["missing_checkout"] = request_count
    if submodule_blocked or not local_source_proven:
        counts["missing_submodule_or_git"] = request_count
    if {
        "buggy_verifier_fail",
        "fixed_or_before_plus_patch_verifier_pass",
        "exact_same_verifier_identity",
    } & required_slots:
        counts["missing_verifier_command_output"] = request_count
    if "patch_diff_apply_lineage" in required_slots:
        counts["missing_patch_lineage"] = request_count
    if "same_source_lineage" in required_slots or "ordered_patch_effect_causality" in required_slots:
        counts["missing_same_source_causality"] = request_count
    counts["java_only_not_multilingual"] = sum(
        1
        for item in work_items
        if item.get("language_bucket") == "single_jvm_java_only_not_multilingual_coverage"
    )
    return counts


def main() -> int:
    stage12462_summary = read_json(STAGE12462_SUMMARY)
    work_items = read_jsonl(STAGE12462_ITEMS)
    stage12327_rows = read_jsonl(STAGE12327_CANDIDATES)
    hydration_summary = read_json(STAGE12333_HYDRATION_SUMMARY, required=False)
    blocker_audit = read_json(STAGE12336_BLOCKER_AUDIT, required=False)

    stage12462_blockers = validate_stage12462(stage12462_summary, work_items)
    blocker_counts = build_blocker_counts(
        work_items, stage12462_blockers, hydration_summary, blocker_audit
    )
    feasible_now = all(count == 0 for count in blocker_counts.values())
    private_executor_request_ready = feasible_now and not stage12462_blockers
    next_stage = (
        "execution_request"
        if feasible_now
        else "source_acquisition_or_hydration_repair_request"
    )
    decision = (
        "local_execution_feasible_request_ready"
        if private_executor_request_ready
        else "blocked_fail_closed_prerequisites_not_proven"
    )

    work_order_item_refs = [
        str(item.get("work_order_item_ref_hash") or "") for item in work_items
    ]
    artifact = {
        "stage": STAGE,
        "record_type": "stage12463_bears_executor_feasibility_and_blocker_audit_v1",
        "decision": decision,
        "claim_boundary": (
            "Feasibility audit only. No checkout, test execution, verifier replay, "
            "network access, training, packaging, row admission, or row emission was performed."
        ),
        "work_order_request_count": len(work_items),
        "work_order_request_count_bucket": count_bucket(len(work_items)),
        "local_execution_feasible_now": feasible_now,
        "private_executor_request_ready": private_executor_request_ready,
        "blocker_counts": blocker_counts,
        "blocker_count_buckets": {
            key: count_bucket(value) for key, value in blocker_counts.items()
        },
        "expected_return_path": stage12462_summary.get("expected_return_path"),
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "next_stage_recommendation": next_stage,
        "stage12462_validation_blocker_refs": [
            stable_hash(item) for item in stage12462_blockers
        ],
        "source_evidence": {
            "stage12462_summary_hash": file_hash(STAGE12462_SUMMARY),
            "stage12462_work_items_hash": file_hash(STAGE12462_ITEMS),
            "stage12327_candidates_hash": file_hash(STAGE12327_CANDIDATES),
            "stage12333_hydration_summary_hash": file_hash(STAGE12333_HYDRATION_SUMMARY),
            "stage12336_blocker_audit_hash": file_hash(STAGE12336_BLOCKER_AUDIT),
            "stage12327_candidate_count": len(stage12327_rows),
            "stage12327_candidate_count_bucket": count_bucket(len(stage12327_rows)),
            "work_order_item_ref_hashes_hash": stable_hash(work_order_item_refs),
            "candidate_support_index_hash": stable_hash(candidate_support_by_hash(stage12327_rows)),
        },
        "prerequisite_policy": {
            "all_required_local_source_verifier_prerequisites_must_be_proven_by_existing_artifacts": True,
            "metadata_only_candidates_are_not_execution_evidence": True,
            "java_side_lane_does_not_close_multilingual_gap": True,
            "raw_materials_are_excluded_from_public_outputs": True,
        },
    }

    issues = scan_public(STAGE, artifact)
    artifact["guardrail_scan"] = {
        "scan_scope": "stage12463_public_summary_and_sanitized_audit",
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issue_hashes": [stable_hash(issue) for issue in issues[:50]],
    }
    artifact["guardrail_scan_passed"] = not issues
    artifact["raw_leak_count"] = len(issues)
    if issues:
        artifact["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        artifact["local_execution_feasible_now"] = False
        artifact["private_executor_request_ready"] = False
        artifact["next_stage_recommendation"] = "source_acquisition_or_hydration_repair_request"

    summary_keys = [
        "stage",
        "decision",
        "work_order_request_count",
        "local_execution_feasible_now",
        "private_executor_request_ready",
        "blocker_counts",
        "expected_return_path",
        "external_comparable_repair_credit_count",
        "remaining_external_fail_to_pass_gap",
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
        "emitted_training_rows",
        "sealed_eval_rows",
        "next_stage_recommendation",
        "guardrail_scan_passed",
        "raw_leak_count",
    ]
    summary = {key: artifact[key] for key in summary_keys}
    summary["record_type"] = "stage12463_bears_executor_feasibility_and_blocker_audit_summary_v1"

    summary_issues = scan_public(STAGE, summary)
    if summary_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["local_execution_feasible_now"] = False
        summary["private_executor_request_ready"] = False
        summary["guardrail_scan_passed"] = False
        summary["raw_leak_count"] = len(summary_issues)
        artifact["guardrail_scan_passed"] = False
        artifact["raw_leak_count"] += len(summary_issues)

    write_json(AUDIT_OUT, artifact)
    write_json(SUMMARY_OUT, summary)
    print(SUMMARY_OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
