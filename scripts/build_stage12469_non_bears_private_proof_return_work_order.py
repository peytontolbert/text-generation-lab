#!/usr/bin/env python3
"""Build Stage12469 non-Bears private proof return work order.

This stage emits public-safe, hash-only work orders for private executors. It
does not execute, hydrate, replay, use network, admit, package, or train.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12469_non_bears_private_proof_return_work_order"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12467 = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12467_OUT = ROOT / "runs/local/artifacts" / STAGE12467
STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
REQUEST_ITEMS = STAGE12467_OUT / "proof_request_items.jsonl"
STAGE12467_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12467}.json"
VALIDATOR_CONTRACT = STAGE12468_OUT / "validator_contract.json"
STAGE12468_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12468}.json"

MANIFEST_OUT = OUT_DIR / "work_order_manifest.json"
WORK_ITEMS_OUT = OUT_DIR / "private_return_work_items.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
ARTIFACT_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_RETURN_PATH = (
    "runs/local/artifacts/"
    "stage12467_non_bears_trace_transition_repair_proof_request_preflight/"
    "private_proof_slot_returns.jsonl"
)
EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
MAX_REQUESTS_PER_SHARD = 6

ZERO_FALSE_FLAGS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
}
ZERO_COUNT_FLAGS = {
    "external_comparable_repair_credit_count": 0,
    "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}

FORBIDDEN_PUBLIC_KEYS = {
    "body",
    "cmd",
    "command",
    "commands",
    "commit",
    "commit_sha",
    "content",
    "diff",
    "file_content",
    "file_path",
    "patch",
    "patch_body",
    "path",
    "paths",
    "raw",
    "raw_content",
    "raw_text",
    "repo",
    "repo_id",
    "repo_name",
    "repository",
    "sha",
    "source",
    "source_text",
    "stderr",
    "stdout",
    "text",
    "uri",
    "uris",
    "url",
    "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact)",
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
FORBIDDEN_REASON_RE = re.compile(
    r"pass[_ -]?to[_ -]?pass|metadata(?:[_ -]?only)?|co[_ -]?presence|"
    r"\bcontrol(?:led)?\b|selected[_ -]?test(?:[_ -]?only)?",
    re.IGNORECASE,
)
PLACEHOLDER_VALUES = [
    "",
    "blocked",
    "claim",
    "claimed",
    "claimed_only",
    "equivalent",
    "fail",
    "false",
    "missing",
    "n_a",
    "na",
    "no",
    "none",
    "not_applicable",
    "null",
    "ok",
    "pass",
    "passed",
    "placeholder",
    "present",
    "proven",
    "redacted",
    "tbd",
    "todo",
    "true",
    "unknown",
    "yes",
]
REQUIRED_EXPLICIT_PRESENT_SLOTS = [
    "before_verifier_status_fail",
    "before_status_fail",
    "after_or_before_plus_patch_verifier_status_pass",
    "after_or_before_plus_patch_status_pass",
    "anti_leak_public_rendering_pass",
    "protected_overlap_audit_pass",
]


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


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} must contain a JSON object")
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


def unique_ordered(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str) and value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    is_policy_label = any(
        token in label.lower()
        for token in [
            "policy",
            "rule",
            "rules",
            "reject_if_any",
            "rejection",
            "non_actions",
        ]
    )
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if (
            value != EXPECTED_RETURN_PATH
            and not is_policy_label
            and RAW_LEAK_RE.search(value)
        ):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
        if not is_policy_label and FORBIDDEN_REASON_RE.search(value):
            issues.append(f"{label}:forbidden_reason_family:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def validate_inputs(
    request_rows: list[dict[str, Any]],
    request_summary: dict[str, Any],
    validator_contract: dict[str, Any],
    validator_summary: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if request_summary.get("stage") != STAGE12467:
        blockers.append("stage12467_summary_unexpected_stage")
    if request_summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12467_guardrail_scan_not_passed")
    if request_summary.get("request_item_count") != len(request_rows):
        blockers.append("stage12467_request_item_count_mismatch")
    if request_summary.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12467_requested_status_family_invalid")
    for key, expected in ZERO_FALSE_FLAGS.items():
        if request_summary.get(key) is not expected:
            blockers.append(f"stage12467_{key}_not_{str(expected).lower()}")
    for key, expected in ZERO_COUNT_FLAGS.items():
        if request_summary.get(key) != expected:
            blockers.append(f"stage12467_{key}_not_{expected}")

    if validator_contract.get("stage") != STAGE12468:
        blockers.append("stage12468_contract_unexpected_stage")
    if validator_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12468_contract_status_family_invalid")
    if validator_contract.get("inputs", {}).get("optional_private_return_jsonl") != EXPECTED_RETURN_PATH:
        blockers.append("stage12468_contract_return_path_mismatch")
    if validator_summary.get("stage") != STAGE12468:
        blockers.append("stage12468_summary_unexpected_stage")
    stage12468_missing_returns_only = (
        validator_summary.get("return_file_present") is False
        and validator_summary.get("raw_leak_count") == 0
        and validator_summary.get("rejected_return_reasons") == {"private_return_file_missing": 1}
        and str(validator_summary.get("decision") or "").startswith("blocked_no_returns")
    )
    if (
        validator_summary.get("guardrail_scan_passed") is not True
        and not stage12468_missing_returns_only
    ):
        blockers.append("stage12468_guardrail_scan_not_passed")
    for key, expected in ZERO_FALSE_FLAGS.items():
        if validator_summary.get(key) is not expected:
            blockers.append(f"stage12468_{key}_not_{str(expected).lower()}")
    for key, expected in ZERO_COUNT_FLAGS.items():
        if validator_summary.get(key) != expected:
            blockers.append(f"stage12468_{key}_not_{expected}")

    allowed_lane_refs = set(validator_contract.get("allowed_lane_refs") or [])
    valid_language_labels = set(validator_contract.get("valid_language_labels") or [])
    for row in request_rows:
        if row.get("lane_ref") not in allowed_lane_refs:
            blockers.append("request_lane_ref_not_allowed_by_stage12468_contract")
        if row.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
            blockers.append("request_status_family_not_external_comparable_fail_to_pass")
        language_hint = row.get("language_priority_hint")
        if language_hint not in valid_language_labels:
            blockers.append("request_language_hint_not_valid_stage12468_label")
        for key in [
            "training_allowed_before_validator",
            "admission_allowed_before_validator",
            "execution_allowed_by_stage12467",
            "hydration_allowed_by_stage12467",
        ]:
            if row.get(key) is not False:
                blockers.append(f"request_{key}_not_false")
        if row.get("credit_before_validator") != 0:
            blockers.append("request_credit_before_validator_not_zero")

    return sorted(set(blockers))


def required_slots_for_item(
    row: dict[str, Any],
    common_slots: list[str],
    lane_specific_slots: dict[str, list[str]],
) -> tuple[list[str], list[str]]:
    lane_ref = str(row.get("lane_ref") or "")
    item_common_slots = row.get("required_proof_slots")
    if isinstance(item_common_slots, list):
        common = unique_ordered([*common_slots, *item_common_slots])
    else:
        common = common_slots
    lane_slots = unique_ordered(lane_specific_slots.get(lane_ref, []))
    return common, lane_slots


def build_work_item(
    row: dict[str, Any],
    index: int,
    validator_contract: dict[str, Any],
) -> dict[str, Any]:
    common_slots = unique_ordered(validator_contract.get("required_proof_slots") or [])
    lane_specific_by_ref = validator_contract.get("lane_specific_required_proof_slots") or {}
    if not isinstance(lane_specific_by_ref, dict):
        lane_specific_by_ref = {}
    lane_ref = str(row.get("lane_ref") or "")
    item_common_slots, lane_specific_slots = required_slots_for_item(
        row, common_slots, lane_specific_by_ref
    )
    combined_slots = unique_ordered([*item_common_slots, *lane_specific_slots])
    proof_request_id = str(row.get("proof_request_id") or "")
    language_label = str(row.get("language_priority_hint") or "")
    return {
        "record_type": "stage12469_private_return_work_item_hash_only_v1",
        "work_order_item_ref_hash": stable_hash(
            {
                "proof_request_id": proof_request_id,
                "lane_ref": lane_ref,
                "language_label": language_label,
                "index": index,
            }
        ),
        "proof_request_id": proof_request_id,
        "proof_request_ref_hash": stable_hash(proof_request_id),
        "lane_ref": lane_ref,
        "lane_ref_hash": stable_hash(lane_ref),
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "language_priority_hint": language_label,
        "language_priority_hint_hash": stable_hash(language_label),
        "language_family_label": None,
        "candidate_language_verified": False,
        "expected_return_language_family_label_must_be_verified": True,
        "required_common_slots": item_common_slots,
        "required_lane_specific_slots": lane_specific_slots,
        "required_combined_slots": combined_slots,
        "required_explicit_present_slots": REQUIRED_EXPLICIT_PRESENT_SLOTS,
        "allowed_return_top_level_keys": sorted(
            validator_contract.get("allowed_return_top_level_keys") or []
        ),
        "required_return_fields": sorted(
            validator_contract.get("required_return_fields") or []
        ),
        "required_return_fields": sorted(
            validator_contract.get("required_return_fields") or []
        ),
        "valid_language_labels": sorted(validator_contract.get("valid_language_labels") or []),
        "slot_status_required_literal": "present",
        "slot_hash_placeholder_rejection_rules": [
            "each_required_combined_slot_must_have_a_slot_hash_value",
            "hash_values_must_be_24_32_40_64_hex_or_sha256_colon_64_hex",
            "empty_missing_unknown_placeholder_redacted_tbd_todo_claimed_true_false_pass_fail_and_equivalents_rejected",
            "single_repeated_character_hashes_rejected",
            "slot_statuses_other_than_literal_present_rejected",
        ],
        "reject_if_any": row.get("reject_if_any") or [],
        "expected_return_path": EXPECTED_RETURN_PATH,
        "return_must_be_validator_compatible_with_stage": STAGE12468,
        "public_safe_policy": "hashes_counts_labels_statuses_and_blocker_codes_only_no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        "non_actions": validator_contract.get("non_actions") or [],
        "private_executor_action_boundary": {
            "stage12469_does_not_execute": True,
            "stage12469_does_not_hydrate": True,
            "stage12469_does_not_replay": True,
            "stage12469_does_not_use_network": True,
            "stage12469_does_not_train": True,
            "stage12469_does_not_admit": True,
            "stage12469_does_not_package": True,
        },
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
    }


def build_shards(work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shard_refs: list[dict[str, Any]] = []
    for shard_index, start in enumerate(range(0, len(work_items), MAX_REQUESTS_PER_SHARD), 1):
        shard_items = work_items[start : start + MAX_REQUESTS_PER_SHARD]
        shard_name = f"private_return_work_order_shard_{shard_index:02d}.json"
        shard = {
            "stage": STAGE,
            "record_type": "stage12469_private_return_work_order_shard_v1",
            "shard_id": f"stage12469_non_bears_private_return_shard_{shard_index:02d}",
            "request_count": len(shard_items),
            "max_requests_per_shard": MAX_REQUESTS_PER_SHARD,
            "work_order_item_ref_hashes": [
                item["work_order_item_ref_hash"] for item in shard_items
            ],
            "proof_request_ids": [item["proof_request_id"] for item in shard_items],
            "lane_refs": sorted({item["lane_ref"] for item in shard_items}),
            "expected_return_path": EXPECTED_RETURN_PATH,
            "public_safe_policy": "hash_only_no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
            "training_allowed": False,
            "admission_allowed": False,
            "packaging_allowed": False,
            "execution_performed_by_stage": False,
            "hydration_performed_by_stage": False,
            "replay_performed_by_stage": False,
        }
        shard["shard_hash"] = stable_hash(shard)
        write_json(OUT_DIR / shard_name, shard)
        shard_refs.append(
            {
                "shard_id": shard["shard_id"],
                "shard_artifact_ref": f"stage12469_{shard_name}",
                "request_count": len(shard_items),
                "shard_hash": shard["shard_hash"],
            }
        )
    return shard_refs


def language_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        label = row.get("language_priority_hint")
        if isinstance(label, str) and label:
            counts[label] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    request_rows = read_jsonl(REQUEST_ITEMS)
    request_summary = read_json(STAGE12467_SUMMARY)
    validator_contract = read_json(VALIDATOR_CONTRACT)
    validator_summary = read_json(STAGE12468_SUMMARY)

    blockers = validate_inputs(
        request_rows, request_summary, validator_contract, validator_summary
    )
    work_items = [
        build_work_item(row, index, validator_contract)
        for index, row in enumerate(request_rows, 1)
    ]
    shard_refs = build_shards(work_items)

    common_slots = unique_ordered(validator_contract.get("required_proof_slots") or [])
    lane_specific_slots = validator_contract.get("lane_specific_required_proof_slots") or {}
    if not isinstance(lane_specific_slots, dict):
        lane_specific_slots = {}
    active_lane_refs = sorted({str(row.get("lane_ref")) for row in request_rows if row.get("lane_ref")})
    lane_specific_slots = {lane: slots for lane, slots in lane_specific_slots.items() if lane in active_lane_refs}

    manifest = {
        "stage": STAGE,
        "record_type": "stage12469_non_bears_private_proof_return_work_order_manifest_v1",
        "decision": (
            "fail_closed_private_return_work_order_ready_zero_credit"
            if not blockers
            else "blocked_private_return_work_order_zero_credit"
        ),
        "claim_boundary": (
            "Work-order artifact only. Stage12469 produces hash-only private "
            "return instructions and performs no private execution, hydration, "
            "replay, network access, admission, packaging, or training."
        ),
        "source_stage_refs": [STAGE12467, STAGE12468],
        "request_count": len(work_items),
        "stage12467_request_item_count": request_summary.get("request_item_count"),
        "request_count_matches_stage12467": len(work_items)
        == request_summary.get("request_item_count"),
        "request_count_bucket": count_bucket(len(work_items)),
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "language_counts": language_counts(request_rows),
        "allowed_lane_refs": sorted(validator_contract.get("allowed_lane_refs") or []),
        "required_common_slots": common_slots,
        "active_lane_refs": active_lane_refs,
        "lane_specific_required_slots": lane_specific_slots,
        "required_explicit_present_slots": REQUIRED_EXPLICIT_PRESENT_SLOTS,
        "allowed_return_top_level_keys": sorted(
            validator_contract.get("allowed_return_top_level_keys") or []
        ),
        "valid_language_labels": sorted(validator_contract.get("valid_language_labels") or []),
        "slot_acceptance_rules": validator_contract.get("slot_acceptance_rules") or [],
        "placeholder_hash_rejection_rules": {
            "placeholder_values_rejected": PLACEHOLDER_VALUES,
            "non_string_hashes_rejected": True,
            "malformed_hash_candidates_rejected": "must_match_24_32_40_64_hex_or_sha256_colon_64_hex",
            "whitespace_hashes_rejected": True,
            "non_hex_or_unapproved_ref_shapes_rejected": True,
            "dummy_repeated_hashes_rejected": True,
        },
        "expected_return_path": EXPECTED_RETURN_PATH,
        "expected_return_path_is_exact_stage12468_validator_input": True,
        "executor_contract": {
            "write_return_rows_to_expected_return_path": True,
            "return_rows_must_use_only_allowed_top_level_keys": True,
            "return_rows_must_use_only_valid_language_labels": True,
            "language_priority_hint_is_not_verified_language_evidence": True,
            "return_rows_must_include_all_required_common_and_lane_specific_slots": True,
            "return_rows_must_use_literal_present_for_required_slot_statuses": True,
            "return_rows_must_use_non_placeholder_hashes_for_required_slot_hashes": True,
            "proof_complete_must_fail_closed_unless_all_required_slots_are_present": True,
            "stage12468_validator_must_validate_before_any_credit_claim": True,
        },
        "non_actions": validator_contract.get("non_actions") or [],
        "public_safe_policy": "no raw paths/urls/commands/shas/repo names/diffs/stdout/stderr/source in public artifacts except the exact declared private return artifact path",
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "artifact_refs": {
            "work_order_manifest": "stage12469_work_order_manifest_json",
            "private_return_work_items": "stage12469_private_return_work_items_jsonl",
            "guardrail_scan": "stage12469_guardrail_scan_json",
            "summary": "stage12469_summary_json",
            "shards": [row["shard_artifact_ref"] for row in shard_refs],
        },
        "shard_policy": {
            "enabled": True,
            "max_requests_per_shard": MAX_REQUESTS_PER_SHARD,
            "shard_count": len(shard_refs),
            "shards": shard_refs,
        },
        "blockers": blockers,
        "source_input_hashes": {
            "stage12467_request_items": file_hash(REQUEST_ITEMS),
            "stage12467_summary": file_hash(STAGE12467_SUMMARY),
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT),
            "stage12468_summary": file_hash(STAGE12468_SUMMARY),
        },
    }

    public_payload = {
        "manifest": manifest,
        "work_items": work_items,
        "shards": shard_refs,
    }
    scan_issues = scan_public("stage12469_public_artifacts", public_payload)
    if scan_issues:
        blockers.append("stage12469_public_guardrail_scan_failed")
        manifest["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"

    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12469_guardrail_scan_v1",
        "scan_scope": "stage12469_public_manifest_work_items_and_shards",
        "policy": "public_safe_hash_status_label_ref_counts_only_no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        "declared_private_return_path_exception": EXPECTED_RETURN_PATH,
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "schema_issue_count": len(blockers),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "blocker_codes": sorted(set(blockers)),
    }
    manifest["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    manifest["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    manifest["schema_issue_count"] = guardrail_scan["schema_issue_count"]
    manifest["artifact_hashes"] = {
        "private_return_work_items": stable_hash(work_items),
        "shards": stable_hash(shard_refs),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    manifest["work_order_manifest_hash"] = stable_hash(
        {key: value for key, value in manifest.items() if key != "work_order_manifest_hash"}
    )

    summary = dict(manifest)
    summary["record_type"] = "stage12469_non_bears_private_proof_return_work_order_summary_v1"
    summary["summary_hash"] = stable_hash(
        {
            "decision": summary["decision"],
            "request_count": summary["request_count"],
            "shard_count": summary["shard_policy"]["shard_count"],
            "blockers": summary["blockers"],
            "raw_leak_count": summary["raw_leak_count"],
            "schema_issue_count": summary["schema_issue_count"],
        }
    )

    write_jsonl(WORK_ITEMS_OUT, work_items)
    write_json(MANIFEST_OUT, manifest)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(ARTIFACT_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "request_count": summary["request_count"],
                "shard_count": summary["shard_policy"]["shard_count"],
                "external_comparable_repair_credit_count": 0,
                "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
                "emitted_training_rows": 0,
                "sealed_eval_rows": 0,
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "schema_issue_count": summary["schema_issue_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
