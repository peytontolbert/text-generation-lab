#!/usr/bin/env python3
"""Attempt Stage12468 private return materialization from current private locator sidecars.

This stage may inspect private locator-sidecar structure, but it emits only
public-safe blocker hashes/counts. It does not write the Stage12468 return file
unless all required proof slots are available. Current expected result is a
fail-closed blocker packet because locator sidecars are not proof bundles.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12481_private_return_materialization_attempt"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12471 = "stage12471_private_source_locator_index_preflight"
STAGE12472 = "stage12472_locator_augmented_non_bears_work_order"
STAGE12478 = "stage12478_private_return_fill_packet"

VALIDATOR_CONTRACT_IN = ROOT / "runs/local/artifacts" / STAGE12468 / "validator_contract.json"
PRIVATE_LOCATOR_IN = ROOT / "runs/local/artifacts" / STAGE12471 / "private_source_locator_index.raw_private.jsonl"
AUGMENTED_ITEMS_IN = ROOT / "runs/local/artifacts" / STAGE12472 / "locator_augmented_work_items.jsonl"
FILL_PACKET_IN = ROOT / "runs/local/artifacts" / STAGE12478 / "private_return_fill_packet_items_ref.jsonl"
STAGE12478_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12478}.json"

MATERIALIZATION_BLOCKERS_OUT = OUT_DIR / "private_return_materialization_blockers_ref.jsonl"
COMPLETE_RETURNS_OUT = OUT_DIR / "validator_complete_private_returns_candidate.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
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
}
# Slots for which the current locator sidecar can supply logistics, not proof.
LOCATOR_SIDE_CANDIDATE_SLOTS = {
    "source_root_label_hash",
    "language_family_label",
}
REQUIRED_PROOF_BUNDLE_SLOTS = {
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
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|"
    r"materialization|blocker|missing|complete|credit|authority)",
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
            value["_stage12481_input_line_index"] = line_no
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


def blocker_row(fill_row: dict[str, Any], private_by_work: dict[str, dict[str, Any]], required_slots: list[str]) -> dict[str, Any]:
    work_hash = fill_row.get("work_order_item_ref_hash")
    private_row = private_by_work.get(work_hash) or {}
    sidecar_logistics_available = bool(private_row)
    present_sidecar_slots = sorted(LOCATOR_SIDE_CANDIDATE_SLOTS if sidecar_logistics_available else [])
    missing_slots = [slot for slot in required_slots if slot not in present_sidecar_slots]
    return {
        "record_type": "stage12481_private_return_materialization_blocker_ref_hash_only_v1",
        "fill_packet_item_ref_hash": fill_row.get("fill_packet_item_ref_hash"),
        "work_order_item_ref_hash": work_hash,
        "proof_request_ref_hash": fill_row.get("proof_request_ref_hash"),
        "proof_request_id_hash": fill_row.get("proof_request_id_hash"),
        "lane_ref_hash": fill_row.get("lane_ref_hash"),
        "language_family_label_hash": fill_row.get("language_family_label_hash"),
        "private_locator_sidecar_present": sidecar_logistics_available,
        "sidecar_logistics_slot_count": len(present_sidecar_slots),
        "required_proof_slot_count": len(required_slots),
        "missing_required_proof_slot_count": len(missing_slots),
        "missing_required_proof_slots_ref_hash": stable_hash(missing_slots),
        "blocking_reason_codes": [
            "private_locator_sidecar_is_not_stage12468_proof_bundle",
            "before_fail_after_patch_pass_verifier_evidence_missing",
            "patch_diff_apply_causality_state_delta_stop_continue_missing",
        ],
        "validator_complete_return_emitted": False,
        "official_stage12468_return_file_written": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    contract, contract_issues = read_json(VALIDATOR_CONTRACT_IN)
    private_rows, private_issues = read_jsonl(PRIVATE_LOCATOR_IN)
    augmented_rows, augmented_issues = read_jsonl(AUGMENTED_ITEMS_IN)
    fill_rows, fill_issues = read_jsonl(FILL_PACKET_IN)
    stage12478_summary, summary78_issues = read_json(STAGE12478_SUMMARY)

    blockers: list[str] = []
    for prefix, issues in [
        ("stage12468_contract", contract_issues),
        ("stage12471_private_locator", private_issues),
        ("stage12472_augmented_items", augmented_issues),
        ("stage12478_fill_packet", fill_issues),
        ("stage12478_summary", summary78_issues),
    ]:
        blockers.extend(f"{prefix}_{key}" for key in issues)
    if contract.get("stage") != STAGE12468:
        blockers.append("stage12468_contract_unexpected_stage")
    if contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12468_contract_status_family_mismatch")
    if stage12478_summary.get("fill_packet_item_count") != len(fill_rows):
        blockers.append("stage12478_fill_packet_count_mismatch")
    if stage12478_summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12478_guardrail_not_passed")
    if stage12478_summary.get("raw_leak_count") != 0:
        blockers.append("stage12478_raw_leak_count_not_zero")

    required_slots = contract.get("required_proof_slots") if isinstance(contract.get("required_proof_slots"), list) else []
    private_by_work = {row.get("work_order_item_ref_hash"): row for row in private_rows if isinstance(row.get("work_order_item_ref_hash"), str)}
    blocker_rows = [] if blockers else [blocker_row(row, private_by_work, required_slots) for row in fill_rows]
    complete_returns: list[dict[str, Any]] = []

    language_counts: Counter[str] = Counter()
    for row in private_rows:
        label = row.get("language_family_label")
        if isinstance(label, str) and label:
            language_counts[label] += 1

    summary = {
        "stage": STAGE,
        "record_type": "stage12481_private_return_materialization_attempt_summary_v1",
        "decision": "blocked_private_locator_sidecars_lack_required_proof_bundle_zero_returns" if blocker_rows and not complete_returns and not blockers else "blocked_private_return_materialization_attempt_zero_credit",
        "claim_boundary": "Materialization attempt only. It emits no raw private evidence and writes no official Stage12468 return file unless all required proof slots are available.",
        "source_stage_refs": [STAGE12478, STAGE12472, STAGE12471, STAGE12468],
        "fill_packet_item_count": len(fill_rows),
        "private_locator_sidecar_count": len(private_rows),
        "private_locator_sidecar_language_counts": dict(sorted(language_counts.items())),
        "augmented_work_item_count": len(augmented_rows),
        "required_proof_slot_count": len(required_slots),
        "locator_logistics_candidate_slot_count": len(LOCATOR_SIDE_CANDIDATE_SLOTS),
        "proof_bundle_required_slot_count": len(REQUIRED_PROOF_BUNDLE_SLOTS),
        "validator_complete_return_candidate_count": len(complete_returns),
        "materialization_blocker_count": len(blocker_rows),
        "official_stage12468_return_file_written": False,
        "missing_proof_bundle_categories": [
            "before_fail_verifier_output",
            "after_or_before_plus_patch_pass_verifier_output",
            "patch_diff_and_apply_result",
            "same_verifier_identity_and_relevance",
            "ordered_patch_before_pass_causality",
            "state_before_after_semantic_codes",
            "candidate_action_set",
            "stop_continue_label",
            "anti_leak_and_protected_overlap_evidence",
        ],
        "stage_blockers": sorted(set(blockers)),
        "next_required_actions": [
            "use_private_executor_to_collect_full_stage12468_proof_bundle_for_each_fill_packet_item",
            "do_not_write_private_proof_slot_returns_jsonl_until_all_required_slots_are_real_hashes",
            "rerun_stage12468_only_after_validator_complete_return_candidates_exist",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "artifact_refs": {
            "private_return_materialization_blockers_ref": "stage12481_private_return_materialization_blockers_ref_jsonl",
            "validator_complete_private_returns_candidate": "stage12481_validator_complete_private_returns_candidate_empty_jsonl",
            "guardrail_scan": "stage12481_guardrail_scan_json",
            "local_summary": "stage12481_local_summary_json",
            "summary": "stage12481_summary_json",
        },
        "input_artifact_hashes": {
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT_IN),
            "stage12471_private_locator_index_raw_private": file_hash(PRIVATE_LOCATOR_IN),
            "stage12472_augmented_items": file_hash(AUGMENTED_ITEMS_IN),
            "stage12478_fill_packet": file_hash(FILL_PACKET_IN),
            "stage12478_summary": file_hash(STAGE12478_SUMMARY),
        },
    }

    public_payload = {
        "summary": summary,
        "materialization_blockers": blocker_rows,
        "complete_returns": complete_returns,
    }
    scan_issues = public_scan("stage12481_public_artifacts", public_payload)
    guardrail = {
        "stage": STAGE,
        "record_type": "stage12481_guardrail_scan_v1",
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
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12481_public_guardrail_scan_failed"]))
        complete_returns = []
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = guardrail["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "validator_complete_return_candidate_count": len(complete_returns),
        "materialization_blocker_count": len(blocker_rows),
        "raw_leak_count": summary["raw_leak_count"],
    })
    summary["artifact_hashes"] = {
        "private_return_materialization_blockers_ref": stable_hash(blocker_rows),
        "validator_complete_private_returns_candidate": stable_hash(complete_returns),
        "guardrail_scan": stable_hash(guardrail),
    }

    write_jsonl(MATERIALIZATION_BLOCKERS_OUT, blocker_rows)
    write_jsonl(COMPLETE_RETURNS_OUT, complete_returns)
    write_json(GUARDRAIL_OUT, guardrail)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "fill_packet_item_count": len(fill_rows),
        "private_locator_sidecar_count": len(private_rows),
        "validator_complete_return_candidate_count": len(complete_returns),
        "materialization_blocker_count": len(blocker_rows),
        "official_stage12468_return_file_written": False,
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
