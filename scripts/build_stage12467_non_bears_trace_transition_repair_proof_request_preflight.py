#!/usr/bin/env python3
"""Build Stage12467 non-Bears repair proof request preflight.

This stage is intentionally fail-closed. It does not mine raw traces, execute
commands, hydrate repositories, admit rows, or grant repair credit. It converts
the Stage12466 pivot decision into a bounded private proof-slot request for
non-Bears source lanes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

PIVOT_SUMMARY = (
    ROOT / "runs/summaries/stage12466_external_repair_source_pivot_control.json"
)

DECISION = "proof_request_preflight_ready_no_execution_no_admission"
TARGET_EXTERNAL_FAIL_TO_PASS_GAP = 15

ZERO_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
    "external_comparable_repair_credit_count": 0,
    "external_fail_to_pass_admitted_count": 0,
    "remaining_external_fail_to_pass_gap": TARGET_EXTERNAL_FAIL_TO_PASS_GAP,
}

REQUIRED_PROOF_SLOTS = [
    "source_root_label_hash",
    "language_family_label",
    "buggy_state_ref_hash",
    "fixed_or_patch_state_ref_hash",
    "checkout_before_ref_hash",
    "checkout_after_or_solution_ref_hash",
    "patch_ref_hash",
    "patch_diff_ref_hash",
    "patch_apply_result_ref_hash",
    "same_source_verifier_identity_hash",
    "same_verifier_identity_ref_hash",
    "before_verifier_command_ref_hash",
    "before_verifier_output_ref_hash",
    "verifier_output_ref_hashes",
    "before_verifier_status_fail",
    "before_status_fail",
    "after_or_before_plus_patch_verifier_command_ref_hash",
    "after_or_before_plus_patch_verifier_output_ref_hash",
    "after_or_before_plus_patch_verifier_status_pass",
    "after_or_before_plus_patch_status_pass",
    "verifier_relevance_ref_hash",
    "ordered_patch_before_pass_causality_ref_hash",
    "state_before_semantic_codes_ref_hash",
    "state_after_semantic_codes_ref_hash",
    "candidate_action_set_ref_hash",
    "stop_continue_label_ref_hash",
    "anti_leak_public_rendering_pass",
    "protected_overlap_audit_pass",
]

FORBIDDEN_LANE_REFS = {
    "lane_ref_bears_failing_passing_private_hydration",
    "lane_ref_controlled_or_mutation_support",
    "lane_ref_selected_test_verifier_observation",
    "lane_ref_pass_to_pass",
    "lane_ref_commit_pair_replay_cache",
    "lane_ref_co_presence_only_or_identity_only",
}

FORBIDDEN_PUBLIC_KEYS = {
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
    "source_text",
    "repo",
    "repo_id",
    "repo_name",
    "repository",
    "sha",
    "commit",
}
KEY_ALLOW_RE = re.compile(
    r"(hash|hashes|ref|refs|stage|schema|slot|slots|policy|guardrail|"
    r"requirement|status|bucket|count)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b|"
    r"\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\b",
    re.IGNORECASE | re.MULTILINE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_locator_or_source_identifier:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def make_request_items(ranked_lanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    request_plan = [
        {
            "lane_ref": "lane_ref_non_bears_trace_transition_repair_proof_preflight",
            "request_count": 12,
            "language_priority": [
                "rust",
                "c_cpp",
                "web_js_ts_html",
                "python",
            ],
            "purpose": "authoritative_replay_or_trace_private_review_for_external_fail_to_pass_patch_effect",
        },
        {
            "lane_ref": "lane_ref_non_bears_external_benchmark_patch_log_preflight",
            "request_count": 6,
            "language_priority": [
                "c_cpp",
                "rust",
                "web_js_ts_html",
                "python",
            ],
            "purpose": "patch_log_private_review_for_same_verifier_before_fail_after_pass",
        },
        {
            "lane_ref": "lane_ref_non_bears_private_review_pivot_preflight",
            "request_count": 4,
            "language_priority": [
                "rust",
                "c_cpp",
                "web_js_ts_html",
                "python",
            ],
            "purpose": "small_private_packet_pivot_when_unique_patch_verifier_binding_exists",
        },
    ]
    available = {row.get("lane_ref"): row for row in ranked_lanes}
    items: list[dict[str, Any]] = []
    for lane_plan in request_plan:
        lane_ref = lane_plan["lane_ref"]
        if lane_ref not in available:
            continue
        for index in range(lane_plan["request_count"]):
            language_hint = lane_plan["language_priority"][
                index % len(lane_plan["language_priority"])
            ]
            items.append(
                {
                    "proof_request_id": stable_hash(
                        {"lane_ref": lane_ref, "index": index, "language": language_hint}
                    ),
                    "lane_ref": lane_ref,
                    "source_stage_refs": available[lane_ref].get("source_stage_refs", []),
                    "language_priority_hint": language_hint,
                    "requested_status_family": "external_comparable_fail_to_pass",
                    "credit_before_validator": 0,
                    "training_allowed_before_validator": False,
                    "admission_allowed_before_validator": False,
                    "execution_allowed_by_stage12467": False,
                    "hydration_allowed_by_stage12467": False,
                    "required_proof_slots": REQUIRED_PROOF_SLOTS,
                    "reject_if_any": [
                        "metadata_only",
                        "patch_verifier_co_presence_only",
                        "pass_to_pass_only",
                        "controlled_or_mutation_fixture_only",
                        "selected_test_observation_without_patch_effect",
                        "cross_source_join",
                        "before_status_not_fail",
                        "after_status_not_pass",
                        "same_verifier_identity_missing",
                        "verifier_relevance_missing",
                        "raw_public_locator_or_text_required",
                    ],
                    "private_return_contract": {
                        "allowed_public_return": "slot_statuses_and_slot_hashes_only",
                        "slot_status_values": ["present", "missing", "blocked", "not_applicable"],
                        "credit_condition": "request_capacity_is_not_repair_proof; all_required_slots_present_with_non_placeholder_hashes_then_stage12468_validator_only",
                    },
                }
            )
    return items


def schema_issues(summary: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, expected in ZERO_GUARDS.items():
        if summary.get(key) != expected:
            issues.append(f"{key}_expected_{expected!r}_got_{summary.get(key)!r}")
    if summary.get("decision") != DECISION:
        issues.append("decision_not_fail_closed_preflight")
    if summary.get("request_item_count", 0) <= 0:
        issues.append("request_item_count_zero")
    if summary.get("credit_claim_requires_next_validator") is not True:
        issues.append("credit_claim_requires_next_validator_not_true")
    if summary.get("forbidden_lane_refs_present"):
        issues.append("forbidden_lane_refs_present")
    counts = summary.get("request_language_priority_counts")
    if not isinstance(counts, dict):
        issues.append("request_language_priority_counts_missing")
    else:
        for language in ["rust", "c_cpp", "web_js_ts_html", "python"]:
            if counts.get(language, 0) < 4:
                issues.append(f"{language}_request_priority_count_below_4")
    return issues


def main() -> None:
    pivot = read_json(PIVOT_SUMMARY)
    ranked_lanes = pivot.get("ranked_non_bears_source_lanes") or []
    if not isinstance(ranked_lanes, list):
        ranked_lanes = []

    request_items = make_request_items(ranked_lanes)
    forbidden_present = sorted(
        {
            str(item.get("lane_ref"))
            for item in request_items
            if item.get("lane_ref") in FORBIDDEN_LANE_REFS
        }
    )

    summary: dict[str, Any] = {
        "stage": STAGE,
        "decision": DECISION,
        "source_stage_refs": [
            "stage12466_external_repair_source_pivot_control",
            "stage12459_external_comparable_patch_effect_source_preflight",
            "stage12237_current_training_control_board",
            "stage12248_root_supply_discrepancy_audit",
        ],
        "central_research_spine_alignment": {
            "objective": "external_same_source_fail_to_pass_patch_effect_supply",
            "not_objective": [
                "selected_test_support_training",
                "controlled_fixture_credit",
                "metadata_only_trace_scaling",
                "co_presence_patch_verifier_projection",
            ],
            "why": "Stage12458 still has an external comparable FAIL_TO_PASS floor gap of 15.",
        },
        "request_item_count": len(request_items),
        "request_language_priority_counts": {
            language: sum(
                1
                for item in request_items
                if item["language_priority_hint"] == language
            )
            for language in ["rust", "c_cpp", "web_js_ts_html", "python"]
        },
        "requested_status_family": "external_comparable_fail_to_pass",
        "required_proof_slots": REQUIRED_PROOF_SLOTS,
        "request_capacity_is_not_repair_proof": True,
        "forbidden_lane_refs_present": forbidden_present,
        "credit_claim_requires_next_validator": True,
        "next_validator_stage": (
            "stage12468_non_bears_patch_effect_private_return_validator"
        ),
        "recommended_next_stage": (
            "stage12468_non_bears_patch_effect_private_return_validator"
        ),
        **ZERO_GUARDS,
    }

    guardrail_issues = scan_public("stage12467_public_artifacts", {
        "summary": summary,
        "request_items": request_items,
    })
    structural_issues = schema_issues(summary)
    guardrail_scan = {
        "stage": STAGE,
        "scan_scope": "stage12467_public_artifacts",
        "policy": "public_safe_refs_only_no_raw_paths_urls_commands_shas_repo_names_diffs_outputs_or_source",
        "scan_passed": not guardrail_issues and not structural_issues,
        "raw_leak_count": len(guardrail_issues),
        "schema_issue_count": len(structural_issues),
        "issues": guardrail_issues,
        "schema_issues": structural_issues,
    }
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = guardrail_scan["schema_issue_count"]
    summary["artifact_hashes"] = {
        "proof_request_items": stable_hash(request_items),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash(summary)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT_DIR / "proof_request_items.jsonl", request_items)
    write_json(OUT_DIR / "proof_request_preflight.json", summary)
    write_json(OUT_DIR / "guardrail_scan.json", guardrail_scan)
    write_json(SUMMARY_OUT, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "request_item_count": summary["request_item_count"],
                "external_comparable_repair_credit_count": summary[
                    "external_comparable_repair_credit_count"
                ],
                "remaining_external_fail_to_pass_gap": summary[
                    "remaining_external_fail_to_pass_gap"
                ],
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "schema_issue_count": summary["schema_issue_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
