#!/usr/bin/env python3
"""Scoped C/C++ locator-gap recovery preflight.

Stage12476 targets only the six C/C++ locator gaps carried by Stage12473/12474.
It inspects public-safe metadata profiles and emits recovery requests when no
existing public-safe locator index can satisfy the gap. It does not execute,
hydrate, replay, use network, train, admit, package, or award repair credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12476_cpp_locator_gap_recovery_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12472 = "stage12472_locator_augmented_non_bears_work_order"
STAGE12474 = "stage12474_private_executor_request_contract"
STAGE12425 = "stage12425_source_adapter_feasibility_miner"
STAGE12426 = "stage12426_sakana_cuda_safe_metadata_profiler"
STAGE12427 = "stage12427_open_swe_safe_metadata_profiler"

STAGE12472_BLOCKED_IN = ROOT / "runs/local/artifacts" / STAGE12472 / "blocked_locator_augmented_requests.jsonl"
STAGE12474_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12474}.json"
STAGE12425_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12425}.json"
STAGE12426_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12426}.json"
STAGE12427_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12427}.json"
STAGE12426_PROFILES = ROOT / "runs/local/artifacts" / STAGE12426 / "safe_metadata_file_profiles.jsonl"
STAGE12427_PROFILES = ROOT / "runs/local/artifacts" / STAGE12427 / "safe_metadata_file_profiles.jsonl"

RECOVERY_REQUESTS_OUT = OUT_DIR / "cpp_private_locator_recovery_requests_ref.jsonl"
RECOVERED_LOCATORS_OUT = OUT_DIR / "cpp_recovered_locator_refs.jsonl"
BLOCKED_RECOVERY_OUT = OUT_DIR / "cpp_locator_recovery_blocked_refs.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
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
    "external_comparable_repair_credit_count": 0,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
    "recovered_actionable_locator_count": 0,
}
FORBIDDEN_PUBLIC_KEYS = {
    "body", "cmd", "command", "commands", "commit", "commit_sha", "content",
    "diff", "file_content", "file_path", "patch", "patch_body", "path",
    "paths", "raw", "raw_content", "raw_text", "repo", "repo_id",
    "repo_name", "repository", "sha", "source", "source_text", "stderr",
    "stdout", "text", "uri", "uris", "url", "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|profile)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|"
    r"stdout|stderr|traceback|terminal output|command output)\\b|"
    r"\\b[0-9a-f]{40}\\b|"
    r"\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b",
    re.IGNORECASE | re.MULTILINE,
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


def read_json(path: Path) -> tuple[dict[str, Any], Counter[str]]:
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return {}, issues
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues[f"{path.name}_invalid_json"] += 1
        return {}, issues
    if not isinstance(value, dict):
        issues[f"{path.name}_not_object"] += 1
        return {}, issues
    return value, issues


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return rows, issues
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["input_jsonl_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["input_jsonl_row_not_object"] += 1
                continue
            value["_stage12476_input_line_index"] = line_no
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def public_scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(f"{label}[{index}]", child))
    return issues


def profile_summary(path: Path) -> dict[str, Any]:
    rows, issues = read_jsonl(path)
    return {
        "profile_artifact_ref_hash": file_hash(path),
        "profile_row_count": len(rows),
        "profile_issue_counts": dict(sorted(issues.items())),
        "profile_candidate_count_sum": sum(int(r.get("candidate_count", 0)) for r in rows if isinstance(r.get("candidate_count", 0), int)),
        "profile_dataset_family_hashes": sorted({stable_hash(r.get("dataset_family")) for r in rows if r.get("dataset_family")}),
        "has_public_safe_source_locator_index": False,
    }


def recovery_request(row: dict[str, Any], profile_refs: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12476_cpp_private_locator_recovery_request_ref_hash_only_v1",
        "recovery_request_ref_hash": stable_hash({
            "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
            "proof_request_ref_hash": row.get("proof_request_ref_hash"),
            "profile_refs": profile_refs,
        }),
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "lane_ref_hash": stable_hash(row.get("lane_ref")),
        "language_priority_hint": "c_cpp",
        "requested_action": "private_locator_index_lookup_required",
        "candidate_source_profile_refs_hash": stable_hash(profile_refs),
        "public_safe_locator_ref_available": False,
        "locator_is_proof": False,
        "proof_status": "none",
        "admission_status": "not_requested",
        "blocker_codes": [
            "metadata_profile_available_but_no_public_safe_locator_index",
            "private_locator_recovery_required",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def blocked_recovery_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12476_cpp_locator_recovery_blocked_ref_hash_only_v1",
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "lane_ref_hash": stable_hash(row.get("lane_ref")),
        "language_priority_hint": "c_cpp",
        "blocked_reason_codes": [
            "no_existing_public_safe_locator_ref_for_cpp_gap",
            "stage12426_12427_metadata_only_not_locator_index",
        ],
        "requires_next_stage": "private_cpp_locator_index_materializer_no_public_raw_leak",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    blocked_rows, blocked_issues = read_jsonl(STAGE12472_BLOCKED_IN)
    stage12474_summary, summary74_issues = read_json(STAGE12474_SUMMARY)
    stage12425_summary, summary25_issues = read_json(STAGE12425_SUMMARY)
    stage12426_summary, summary26_issues = read_json(STAGE12426_SUMMARY)
    stage12427_summary, summary27_issues = read_json(STAGE12427_SUMMARY)

    c_cpp_rows = [row for row in blocked_rows if row.get("language_priority_hint") == "c_cpp"]
    non_c_cpp_rows = [row for row in blocked_rows if row.get("language_priority_hint") != "c_cpp"]

    stage_blockers: list[str] = []
    for prefix, issues in [
        ("stage12472_blocked", blocked_issues),
        ("stage12474_summary", summary74_issues),
        ("stage12425_summary", summary25_issues),
        ("stage12426_summary", summary26_issues),
        ("stage12427_summary", summary27_issues),
    ]:
        stage_blockers.extend(f"{prefix}_{key}" for key in issues)

    if stage12474_summary.get("stage") != STAGE12474:
        stage_blockers.append("stage12474_summary_unexpected_stage")
    if stage12474_summary.get("c_cpp_locator_gap") != len(c_cpp_rows):
        stage_blockers.append("c_cpp_gap_count_mismatch")
    if stage12474_summary.get("guardrail_scan_passed") is not True:
        stage_blockers.append("stage12474_guardrail_not_passed")
    if stage12474_summary.get("raw_leak_count") != 0:
        stage_blockers.append("stage12474_raw_leak_count_not_zero")
    for key, expected in FALSE_GUARDS.items():
        if stage12474_summary.get(key) is not expected:
            stage_blockers.append(f"stage12474_{key}_not_false")
    for key in ["external_comparable_repair_credit_count", "emitted_training_rows", "sealed_eval_rows"]:
        if stage12474_summary.get(key) != 0:
            stage_blockers.append(f"stage12474_{key}_not_zero")

    profile_refs = {
        "stage12426": profile_summary(STAGE12426_PROFILES),
        "stage12427": profile_summary(STAGE12427_PROFILES),
    }
    source_profile_status = {
        "stage12425_decision_ref_hash": stable_hash(stage12425_summary.get("decision")),
        "stage12426_decision_ref_hash": stable_hash(stage12426_summary.get("decision")),
        "stage12427_decision_ref_hash": stable_hash(stage12427_summary.get("decision")),
        "stage12426_candidate_count": stage12426_summary.get("candidate_count", 0),
        "stage12427_candidate_count": stage12427_summary.get("candidate_count", 0),
        "stage12426_metadata_only": stage12426_summary.get("candidate_count_is_training_rows") is False,
        "stage12427_metadata_only": stage12427_summary.get("candidate_count_is_training_rows") is False,
        "existing_public_safe_locator_index_available": False,
    }

    request_rows = [] if stage_blockers else [recovery_request(row, profile_refs) for row in c_cpp_rows]
    recovered_locator_rows: list[dict[str, Any]] = []
    blocked_recovery_rows = [blocked_recovery_ref(row) for row in c_cpp_rows]

    summary = {
        "stage": STAGE,
        "record_type": "stage12476_cpp_locator_gap_recovery_preflight_summary_v1",
        "decision": (
            "cpp_locator_recovery_requests_ready_zero_credit_no_locator_refs"
            if request_rows and not stage_blockers
            else "blocked_cpp_locator_recovery_preflight_zero_credit"
        ),
        "claim_boundary": (
            "Scoped C/C++ locator-gap recovery preflight only. Metadata profiles are "
            "not actionable locators and not proof. This stage emits request refs for a "
            "future private locator materializer and zero recovered locator refs."
        ),
        "source_stage_refs": [STAGE12472, STAGE12474, STAGE12425, STAGE12426, STAGE12427],
        "blocked_refs_seen": len(blocked_rows),
        "c_cpp_locator_gaps_seen": len(c_cpp_rows),
        "non_c_cpp_blocked_refs_skipped": len(non_c_cpp_rows),
        "accepted_refs_carried_forward_context_count": stage12474_summary.get("accepted_locator_work_item_count", 0),
        "request_refs_emitted": len(request_rows),
        "locator_refs_emitted": len(recovered_locator_rows),
        "refs_rejected_total": len(blocked_recovery_rows),
        "refs_rejected_private_or_raw_locator": 0,
        "refs_rejected_requires_execution_or_hydration": 0,
        "refs_rejected_not_public_safe": 0,
        "refs_rejected_language_mismatch": 0,
        "refs_rejected_ambiguous_or_multi_match": 0,
        "refs_rejected_metadata_only_no_locator_index": len(blocked_recovery_rows),
        "source_profile_status": source_profile_status,
        "source_profile_refs": profile_refs,
        "hard_reject_rules": [
            "reject_execution_hydration_replay_network_training_admission_packaging",
            "reject_raw_private_locator_values_repo_names_paths_commands_shas_urls_diffs_stdout_stderr_source",
            "reject_metadata_profile_as_actionable_locator",
            "reject_language_drift_non_cpp_locator",
            "reject_ambiguous_multi_match_without_stable_disambiguator",
            "reject_proof_or_credit_escalation",
        ],
        "next_required_stage": "private_cpp_locator_index_materializer_no_public_raw_leak",
        "stage_blockers": sorted(set(stage_blockers)),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "artifact_refs": {
            "cpp_private_locator_recovery_requests_ref": "stage12476_cpp_private_locator_recovery_requests_ref_jsonl",
            "cpp_recovered_locator_refs": "stage12476_cpp_recovered_locator_refs_jsonl_empty",
            "cpp_locator_recovery_blocked_refs": "stage12476_cpp_locator_recovery_blocked_refs_jsonl",
            "guardrail_scan": "stage12476_guardrail_scan_json",
            "local_summary": "stage12476_local_summary_json",
            "summary": "stage12476_summary_json",
        },
        "input_artifact_hashes": {
            "stage12472_blocked_locator_augmented_requests": file_hash(STAGE12472_BLOCKED_IN),
            "stage12474_summary": file_hash(STAGE12474_SUMMARY),
            "stage12425_summary": file_hash(STAGE12425_SUMMARY),
            "stage12426_summary": file_hash(STAGE12426_SUMMARY),
            "stage12427_summary": file_hash(STAGE12427_SUMMARY),
            "stage12426_safe_metadata_file_profiles": file_hash(STAGE12426_PROFILES),
            "stage12427_safe_metadata_file_profiles": file_hash(STAGE12427_PROFILES),
        },
    }

    public_payload = {
        "cpp_private_locator_recovery_requests_ref": request_rows,
        "cpp_recovered_locator_refs": recovered_locator_rows,
        "cpp_locator_recovery_blocked_refs": blocked_recovery_rows,
        "summary": summary,
    }
    scan_issues = public_scan("stage12476_public_artifacts", public_payload)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12476_guardrail_scan_v1",
        "scan_scope": "stage12476_public_summary_and_hash_only_cpp_locator_recovery_indexes",
        "scan_status": "completed",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }

    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12476_public_guardrail_scan_failed"]))
        request_rows = []
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["artifact_hashes"] = {
        "cpp_private_locator_recovery_requests_ref": stable_hash(request_rows),
        "cpp_recovered_locator_refs": stable_hash(recovered_locator_rows),
        "cpp_locator_recovery_blocked_refs": stable_hash(blocked_recovery_rows),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "c_cpp_locator_gaps_seen": len(c_cpp_rows),
        "request_refs_emitted": len(request_rows),
        "locator_refs_emitted": len(recovered_locator_rows),
        "stage_blockers": summary["stage_blockers"],
        "raw_leak_count": summary["raw_leak_count"],
    })

    write_jsonl(RECOVERY_REQUESTS_OUT, request_rows)
    write_jsonl(RECOVERED_LOCATORS_OUT, recovered_locator_rows)
    write_jsonl(BLOCKED_RECOVERY_OUT, blocked_recovery_rows)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "blocked_refs_seen": len(blocked_rows),
        "c_cpp_locator_gaps_seen": len(c_cpp_rows),
        "request_refs_emitted": len(request_rows),
        "locator_refs_emitted": len(recovered_locator_rows),
        "refs_rejected_metadata_only_no_locator_index": len(blocked_recovery_rows),
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "guardrail_scan_passed": summary["guardrail_scan_passed"],
        "raw_leak_count": summary["raw_leak_count"],
        "schema_issue_count": summary["schema_issue_count"],
        "training_allowed": False,
        "admission_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
