#!/usr/bin/env python3
"""Build Stage12465 Bears source acquisition/hydration executor preflight.

This is a planning/preflight stage only. It does not use network, initialize
submodules, checkout source, hydrate materials, run tests, train, package, or
admit rows. Public artifacts remain hash/bucket/boolean only.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12465_bears_source_acquisition_hydration_executor_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
PLAN_OUT = OUT_DIR / "executor_preflight_plan.json"
REQUIREMENTS_OUT = OUT_DIR / "approval_or_source_requirements.json"
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12464_SUMMARY = (
    ROOT / "runs/summaries/stage12464_bears_source_acquisition_or_hydration_repair_request.json"
)
STAGE12464_WORK_ITEMS = (
    ROOT
    / "runs/local/artifacts/stage12464_bears_source_acquisition_or_hydration_repair_request"
    / "bears_hydration_repair_work_items.jsonl"
)
STAGE12463_SUMMARY = (
    ROOT / "runs/summaries/stage12463_bears_executor_feasibility_and_blocker_audit.json"
)
STAGE12336_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12336_bears_local_hydration_blocker_audit"
    / "bears_local_hydration_blocker_audit.json"
)

EXPECTED_STAGE12464_DECISION = "request_ready_no_execution_no_training"
EXPECTED_STAGE12463_DECISION = "blocked_fail_closed_prerequisites_not_proven"
EXPECTED_STAGE12336_DECISION = "bears_local_hydration_blocked_fail_closed"
BLOCKED_DECISION = "blocked_requires_external_source_or_approval"
EXECUTABLE_DECISION = "executable_without_approval"
NEXT_APPROVAL_ACTION = "request_user_approval_for_source_hydration"
NEXT_PIVOT_ACTION = "pivot_to_non_bears_external_source_lane"

PREREQUISITE_KEYS = [
    "source_materials",
    "submodule_or_git_materials",
    "checkout_materials",
    "verifier_materials",
    "patch_lineage_materials",
    "same_source_causality_materials",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|terminal output|command output|git clone|"
    r"git apply|pytest\s|python -c|bash -|sh -|curl\s|checkout\s|submodule\s)\b|"
    r"\b[0-9a-f]{40}\b",
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
    r"(hash|hashes|ref|refs|schema|slot|slots|blocker|scan|policy|requirement)",
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


def read_json(path: Path) -> dict[str, Any]:
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
    return "25-plus"


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def local_prerequisite_status(
    stage12464: dict[str, Any],
    stage12463: dict[str, Any],
    stage12336: dict[str, Any],
) -> dict[str, bool]:
    stage12464_allows_execution = (
        stage12464.get("next_stage_execution_allowed_by_stage12464") is True
        and stage12464.get("executor_after_acquisition_allowed") is True
    )
    stage12463_feasible = (
        stage12463.get("local_execution_feasible_now") is True
        and stage12463.get("private_executor_request_ready") is True
    )
    stage12336_unblocked = stage12336.get("decision") != EXPECTED_STAGE12336_DECISION
    probe_results = stage12336.get("probe_results") or {}
    git_materials = (
        probe_results.get("bears_dot_git_exists") is True
        and probe_results.get("bears_submodule_path_exists") is True
        and bool(probe_results.get("bears_tree_entry"))
        and bool(probe_results.get("submodule_status"))
    )
    blocker_counts = stage12463.get("blocker_counts") or {}
    no_missing_counts = all(
        blocker_counts.get(key, 0) == 0
        for key in [
            "missing_checkout",
            "missing_submodule_or_git",
            "missing_verifier_command_output",
            "missing_patch_lineage",
            "missing_same_source_causality",
        ]
    )
    proven = stage12464_allows_execution and stage12463_feasible and stage12336_unblocked
    return {
        "source_materials": proven and no_missing_counts,
        "submodule_or_git_materials": proven and git_materials,
        "checkout_materials": proven and blocker_counts.get("missing_checkout", 1) == 0,
        "verifier_materials": proven
        and blocker_counts.get("missing_verifier_command_output", 1) == 0,
        "patch_lineage_materials": proven
        and blocker_counts.get("missing_patch_lineage", 1) == 0,
        "same_source_causality_materials": proven
        and blocker_counts.get("missing_same_source_causality", 1) == 0,
    }


def input_validation_blockers(
    stage12464: dict[str, Any],
    stage12463: dict[str, Any],
    stage12336: dict[str, Any],
    work_items: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if stage12464.get("decision") != EXPECTED_STAGE12464_DECISION:
        blockers.append("stage12464_decision_not_request_ready")
    if stage12463.get("decision") != EXPECTED_STAGE12463_DECISION:
        blockers.append("stage12463_decision_not_expected_fail_closed")
    if stage12336.get("decision") != EXPECTED_STAGE12336_DECISION:
        blockers.append("stage12336_decision_not_expected_blocked")
    if stage12464.get("request_count") != len(work_items):
        blockers.append("stage12464_request_count_mismatch")
    if stage12464.get("guardrail_scan_passed") is not True:
        blockers.append("stage12464_guardrail_not_passed")
    if stage12463.get("guardrail_scan_passed") is not True:
        blockers.append("stage12463_guardrail_not_passed")
    for key in [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
    ]:
        if stage12464.get(key) is not False:
            blockers.append(f"stage12464_{key}_not_false")
        if stage12463.get(key) is not False:
            blockers.append(f"stage12463_{key}_not_false")
    return blockers


def build_missing_requirements(prerequisites: dict[str, bool]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, key in enumerate(PREREQUISITE_KEYS, 1):
        if prerequisites.get(key) is True:
            continue
        rows.append(
            {
                "requirement_ref_hash": stable_hash({"requirement": key}),
                "priority_rank": rank,
                "requirement_bucket": key,
                "currently_proven_locally": False,
                "requires_external_source_or_approval": True,
                "may_be_satisfied_by_existing_private_executor_materials": True,
            }
        )
    return rows


def forbidden_execution_flags() -> dict[str, bool | int]:
    return {
        "execution_performed_by_stage": False,
        "external_comparable_repair_credit_count": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
    }


def main() -> None:
    required_paths = [
        STAGE12464_SUMMARY,
        STAGE12464_WORK_ITEMS,
        STAGE12463_SUMMARY,
        STAGE12336_AUDIT,
    ]
    missing = [path.name for path in required_paths if not path.exists()]
    if missing:
        work_item_count = 0
        prerequisites = {key: False for key in PREREQUISITE_KEYS}
        validation_blockers = ["missing_required_prior_input"]
    else:
        stage12464 = read_json(STAGE12464_SUMMARY)
        stage12463 = read_json(STAGE12463_SUMMARY)
        stage12336 = read_json(STAGE12336_AUDIT)
        work_items = read_jsonl(STAGE12464_WORK_ITEMS)
        work_item_count = len(work_items)
        prerequisites = local_prerequisite_status(stage12464, stage12463, stage12336)
        validation_blockers = input_validation_blockers(
            stage12464, stage12463, stage12336, work_items
        )

    local_prerequisites_present = all(prerequisites.values()) and not validation_blockers
    decision = EXECUTABLE_DECISION if local_prerequisites_present else BLOCKED_DECISION
    requires_external = not local_prerequisites_present
    requires_approval = requires_external
    missing_requirements = build_missing_requirements(prerequisites)
    next_action = NEXT_APPROVAL_ACTION if requires_external else "run_private_executor"

    summary = {
        "record_type": f"{STAGE}_summary_v1",
        "stage": STAGE,
        "decision": decision,
        "work_item_count": work_item_count,
        "work_item_count_bucket": count_bucket(work_item_count),
        "local_prerequisites_present": local_prerequisites_present,
        "requires_network_or_external_source": requires_external,
        "requires_user_approval_for_git_or_network": requires_approval,
        **forbidden_execution_flags(),
        "next_action_recommendation": next_action,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "input_validation_blocker_count": len(validation_blockers),
        "missing_requirement_count": len(missing_requirements),
        "artifact_hashes": {},
    }

    plan = {
        "record_type": f"{STAGE}_executor_preflight_plan_v1",
        "stage": STAGE,
        "decision": decision,
        "claim_boundary": (
            "Preflight plan only; no execution, source acquisition, network use, "
            "hydration, verifier run, training, packaging, row admission, or sealed evaluation."
        ),
        "work_item_count": work_item_count,
        "local_prerequisites_present": local_prerequisites_present,
        "prerequisite_status": prerequisites,
        "blocked_requirement_ref_hashes": [
            row["requirement_ref_hash"] for row in missing_requirements
        ],
        "requires_network_or_external_source": requires_external,
        "requires_user_approval_for_git_or_network": requires_approval,
        **forbidden_execution_flags(),
        "next_action_recommendation": next_action,
        "fallback_next_action_if_bears_scope_remains_too_narrow": NEXT_PIVOT_ACTION,
        "prior_artifact_hashes": {
            "stage12464_summary": file_hash(STAGE12464_SUMMARY),
            "stage12464_work_items": file_hash(STAGE12464_WORK_ITEMS),
            "stage12463_summary": file_hash(STAGE12463_SUMMARY),
            "stage12336_audit": file_hash(STAGE12336_AUDIT),
        },
        "input_validation_blocker_ref_hashes": [
            stable_hash(blocker) for blocker in validation_blockers
        ],
    }

    requirements = {
        "record_type": f"{STAGE}_approval_or_source_requirements_v1",
        "stage": STAGE,
        "decision": decision,
        "work_item_count": work_item_count,
        "local_prerequisites_present": local_prerequisites_present,
        "requires_network_or_external_source": requires_external,
        "requires_user_approval_for_git_or_network": requires_approval,
        "approval_requirement_count": len(missing_requirements),
        "approval_requirements": missing_requirements,
        "approval_scope_buckets": sorted(
            {row["requirement_bucket"] for row in missing_requirements}
        ),
        "private_executor_may_join_raw_materials_after_approval": requires_approval,
        "public_artifacts_include_raw_materials": False,
        **forbidden_execution_flags(),
        "next_action_recommendation": next_action,
        "fallback_next_action_if_bears_scope_remains_too_narrow": NEXT_PIVOT_ACTION,
    }

    public_issues = []
    public_issues.extend(scan_public("plan", plan))
    public_issues.extend(scan_public("requirements", requirements))
    raw_leak_count = len(public_issues)
    guardrail = {
        "scan_passed": raw_leak_count == 0,
        "raw_leak_count": raw_leak_count,
        "issue_ref_hashes": [stable_hash(issue) for issue in public_issues],
        "policy": "hash_bucket_boolean_only_no_raw_paths_commands_urls_repos_shas_diffs_outputs_or_source",
    }

    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = raw_leak_count
    summary["artifact_hashes"] = {
        "executor_preflight_plan": stable_hash(plan),
        "approval_or_source_requirements": stable_hash(requirements),
    }
    if not guardrail["scan_passed"]:
        summary["decision"] = BLOCKED_DECISION

    summary_mirror = {
        key: summary[key]
        for key in [
            "decision",
            "work_item_count",
            "local_prerequisites_present",
            "requires_network_or_external_source",
            "requires_user_approval_for_git_or_network",
            "execution_performed_by_stage",
            "external_comparable_repair_credit_count",
            "training_allowed",
            "admission_allowed",
            "packaging_allowed",
            "emitted_training_rows",
            "sealed_eval_rows",
            "next_action_recommendation",
            "guardrail_scan_passed",
            "raw_leak_count",
        ]
    }
    plan["public_raw_leak_guardrail"] = guardrail
    plan["summary_mirror"] = summary_mirror
    requirements["public_raw_leak_guardrail"] = guardrail
    requirements["summary_mirror"] = summary_mirror
    summary["public_raw_leak_guardrail"] = guardrail

    write_json(PLAN_OUT, plan)
    write_json(REQUIREMENTS_OUT, requirements)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
