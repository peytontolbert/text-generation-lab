#!/usr/bin/env python3
"""Private C/C++ locator sidecar materialization request.

Stage12480 turns Stage12476 C/C++ locator recovery requests into a public-safe
private sidecar fill packet. It does not materialize locators itself, execute,
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
STAGE = "stage12480_private_cpp_locator_sidecar_materializer_request"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12476 = "stage12476_cpp_locator_gap_recovery_preflight"
STAGE12473 = "stage12473_locator_augmented_work_order_preflight"
STAGE12472 = "stage12472_locator_augmented_non_bears_work_order"

STAGE12476_OUT = ROOT / "runs/local/artifacts" / STAGE12476
STAGE12476_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12476}.json"
STAGE12476_REQUESTS = STAGE12476_OUT / "cpp_private_locator_recovery_requests_ref.jsonl"
STAGE12476_BLOCKED = STAGE12476_OUT / "cpp_locator_recovery_blocked_refs.jsonl"
STAGE12473_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12473}.json"
STAGE12472_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12472}.json"

SIDECAR_REQUESTS_OUT = OUT_DIR / "private_cpp_locator_sidecar_fill_requests_ref.jsonl"
SIDECAR_TEMPLATE_OUT = OUT_DIR / "private_cpp_locator_sidecar_template.json"
PUBLIC_LOCATOR_REFS_OUT = OUT_DIR / "public_cpp_locator_refs.jsonl"
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
REQUIRED_LOCATOR_FIELDS = [
    "source_adapter_candidate_ref_hash",
    "private_locator_ref_hash",
    "source_root_label_hash",
    "lane_candidate_family_hash",
    "private_execution_context_ref_hash",
]
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
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|"
    r"sidecar|template|fill|gate|credit|authority|materializer|field)",
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
            value["_stage12480_input_line_index"] = line_no
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


def sidecar_template() -> dict[str, Any]:
    return {
        "record_type": "stage12480_private_cpp_locator_sidecar_template_v1",
        "template_is_public_safe_placeholders_only": True,
        "required_private_sidecar_fields": REQUIRED_LOCATOR_FIELDS,
        "required_private_sidecar_field_count": len(REQUIRED_LOCATOR_FIELDS),
        "required_language_family_label": "c_cpp",
        "public_return_policy": "hash_only_locator_refs_no_raw_values",
        "private_materializer_must_verify": [
            "language_family_is_c_cpp",
            "source_adapter_candidate_ref_is_same_request_lineage",
            "source_root_label_hash_available",
            "lane_candidate_family_hash_available",
            "private_execution_context_ref_hash_available",
            "locator_not_metadata_only",
            "locator_not_proof",
            "no_train_eval_overlap_claimed_by_locator_stage",
        ],
        "hard_reject_rules": [
            "reject_metadata_profile_as_locator",
            "reject_ambiguous_multi_match_without_stable_disambiguator",
            "reject_language_drift_non_cpp_locator",
            "reject_raw_locator_repo_path_command_sha_url_diff_source_stdout_stderr_public_output",
            "reject_execution_hydration_replay_network_training_admission_packaging",
            "reject_proof_or_credit_escalation",
        ],
    }


def fill_request(row: dict[str, Any], template_ref_hash: str) -> dict[str, Any]:
    return {
        "record_type": "stage12480_private_cpp_locator_sidecar_fill_request_ref_hash_only_v1",
        "sidecar_fill_request_ref_hash": stable_hash({
            "recovery_request_ref_hash": row.get("recovery_request_ref_hash"),
            "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
            "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        }),
        "source_recovery_request_ref_hash": row.get("recovery_request_ref_hash"),
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "lane_ref_hash": row.get("lane_ref_hash"),
        "language_priority_hint": "c_cpp",
        "required_private_sidecar_fields_ref_hash": stable_hash(REQUIRED_LOCATOR_FIELDS),
        "private_sidecar_template_ref_hash": template_ref_hash,
        "requested_private_materializer_action": "fill_required_locator_hash_fields_from_real_private_locator_index",
        "public_output_expected_after_fill": "stage12471_style_public_locator_ref_hash_only",
        "locator_is_proof": False,
        "proof_status": "none",
        "admission_status": "not_requested",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    request_rows, request_issues = read_jsonl(STAGE12476_REQUESTS)
    blocked_rows, blocked_issues = read_jsonl(STAGE12476_BLOCKED)
    stage12476_summary, summary76_issues = read_json(STAGE12476_SUMMARY)
    stage12473_summary, summary73_issues = read_json(STAGE12473_SUMMARY)
    stage12472_summary, summary72_issues = read_json(STAGE12472_SUMMARY)

    blockers: list[str] = []
    for prefix, issues in [
        ("stage12476_requests", request_issues),
        ("stage12476_blocked", blocked_issues),
        ("stage12476_summary", summary76_issues),
        ("stage12473_summary", summary73_issues),
        ("stage12472_summary", summary72_issues),
    ]:
        blockers.extend(f"{prefix}_{key}" for key in issues)

    if stage12476_summary.get("stage") != STAGE12476:
        blockers.append("stage12476_summary_unexpected_stage")
    if stage12476_summary.get("request_refs_emitted") != len(request_rows):
        blockers.append("stage12476_request_count_mismatch")
    if stage12476_summary.get("c_cpp_locator_gaps_seen") != len(request_rows):
        blockers.append("stage12476_cpp_gap_count_mismatch")
    if stage12476_summary.get("locator_refs_emitted") != 0:
        blockers.append("stage12476_locator_refs_already_emitted_unexpected")
    if stage12476_summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12476_guardrail_not_passed")
    if stage12476_summary.get("raw_leak_count") != 0:
        blockers.append("stage12476_raw_leak_count_not_zero")
    for key, expected in FALSE_GUARDS.items():
        if stage12476_summary.get(key) is not expected:
            blockers.append(f"stage12476_{key}_not_false")
    for row in request_rows:
        if row.get("language_priority_hint") != "c_cpp":
            blockers.append("request_language_priority_not_c_cpp")
        if row.get("public_safe_locator_ref_available") is not False:
            blockers.append("request_public_safe_locator_ref_available_not_false")
        if row.get("locator_is_proof") is not False:
            blockers.append("request_locator_is_proof_not_false")

    template = sidecar_template()
    template_ref_hash = stable_hash(template)
    fill_rows = [] if blockers else [fill_request(row, template_ref_hash) for row in request_rows]
    public_locator_refs: list[dict[str, Any]] = []

    summary = {
        "stage": STAGE,
        "record_type": "stage12480_private_cpp_locator_sidecar_materializer_request_summary_v1",
        "decision": "private_cpp_locator_sidecar_fill_requests_ready_zero_credit_no_locator_refs" if fill_rows and not blockers else "blocked_private_cpp_locator_sidecar_materializer_request_zero_credit",
        "claim_boundary": "Request-only sidecar materializer packet. No private locator values are emitted and no locator/proof/training credit is awarded.",
        "source_stage_refs": [STAGE12476, STAGE12473, STAGE12472],
        "c_cpp_locator_gap_count": len(request_rows),
        "sidecar_fill_request_count": len(fill_rows),
        "public_cpp_locator_ref_count": len(public_locator_refs),
        "recovered_actionable_locator_count": 0,
        "stage12476_blocked_recovery_ref_count": len(blocked_rows),
        "required_private_sidecar_fields": REQUIRED_LOCATOR_FIELDS,
        "required_private_sidecar_field_count": len(REQUIRED_LOCATOR_FIELDS),
        "private_sidecar_template_ref_hash": template_ref_hash,
        "next_required_actions": [
            "private_materializer_fill_cpp_locator_sidecars_from_real_private_index",
            "emit_stage12471_style_public_locator_refs_after_sidecars_exist",
            "rerun_stage12472_12473_merge_preflight_for_cpp_subset",
            "only_after_locator_preflight_passes_create_cpp_stage12474_style_executor_requests",
        ],
        "hard_reject_rules": template["hard_reject_rules"],
        "stage_blockers": sorted(set(blockers)),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "artifact_refs": {
            "private_cpp_locator_sidecar_fill_requests_ref": "stage12480_private_cpp_locator_sidecar_fill_requests_ref_jsonl",
            "private_cpp_locator_sidecar_template": "stage12480_private_cpp_locator_sidecar_template_json",
            "public_cpp_locator_refs": "stage12480_public_cpp_locator_refs_empty_jsonl",
            "guardrail_scan": "stage12480_guardrail_scan_json",
            "local_summary": "stage12480_local_summary_json",
            "summary": "stage12480_summary_json",
        },
        "input_artifact_hashes": {
            "stage12476_cpp_private_locator_recovery_requests_ref": file_hash(STAGE12476_REQUESTS),
            "stage12476_cpp_locator_recovery_blocked_refs": file_hash(STAGE12476_BLOCKED),
            "stage12476_summary": file_hash(STAGE12476_SUMMARY),
            "stage12473_summary": file_hash(STAGE12473_SUMMARY),
            "stage12472_summary": file_hash(STAGE12472_SUMMARY),
        },
    }

    public_payload = {
        "summary": summary,
        "sidecar_fill_requests": fill_rows,
        "public_cpp_locator_refs": public_locator_refs,
        "sidecar_template": template,
    }
    scan_issues = public_scan("stage12480_public_artifacts", public_payload)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12480_guardrail_scan_v1",
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
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12480_public_guardrail_scan_failed"]))
        fill_rows = []
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "sidecar_fill_request_count": len(fill_rows),
        "public_cpp_locator_ref_count": len(public_locator_refs),
        "stage_blockers": summary["stage_blockers"],
        "raw_leak_count": summary["raw_leak_count"],
    })
    summary["artifact_hashes"] = {
        "private_cpp_locator_sidecar_fill_requests_ref": stable_hash(fill_rows),
        "private_cpp_locator_sidecar_template": stable_hash(template),
        "public_cpp_locator_refs": stable_hash(public_locator_refs),
        "guardrail_scan": stable_hash(guardrail_scan),
    }

    write_jsonl(SIDECAR_REQUESTS_OUT, fill_rows)
    write_json(SIDECAR_TEMPLATE_OUT, template)
    write_jsonl(PUBLIC_LOCATOR_REFS_OUT, public_locator_refs)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "c_cpp_locator_gap_count": len(request_rows),
        "sidecar_fill_request_count": len(fill_rows),
        "public_cpp_locator_ref_count": len(public_locator_refs),
        "recovered_actionable_locator_count": 0,
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
