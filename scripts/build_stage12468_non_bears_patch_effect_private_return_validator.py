#!/usr/bin/env python3
"""Fail-closed validator for Stage12467 non-Bears private proof returns.

The validator reads only the Stage12467 public proof-slot request items and an
optional private return JSONL. It never executes tests, hydrates sources,
applies patches, emits training rows, admits rows, or exposes raw return
content. Accepted output rows are hash-only references.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12468_non_bears_patch_effect_private_return_validator"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12467 = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
REQUEST_ITEMS = ROOT / "runs/local/artifacts" / STAGE12467 / "proof_request_items.jsonl"
REQUEST_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12467}.json"
STAGE12466 = "stage12466_external_repair_source_pivot_control"
PIVOT_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12466}.json"
RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12467 / "private_proof_slot_returns.jsonl"

ACCEPTED_INDEX = OUT_DIR / "accepted_return_ref_index.jsonl"
REJECTED_INDEX = OUT_DIR / "rejected_return_ref_index.jsonl"
CONTRACT_OUT = OUT_DIR / "validator_contract.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
EXACT_PRESENT = "present"
REQUIRED_EXPLICIT_PRESENT_SLOTS = [
    "before_verifier_status_fail",
    "before_status_fail",
    "after_or_before_plus_patch_verifier_status_pass",
    "after_or_before_plus_patch_status_pass",
    "anti_leak_public_rendering_pass",
    "protected_overlap_audit_pass",
]

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
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|"
    r"family|lane|guardrail|issue|reason|count|policy|allowed|proof)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_REASON_RE = re.compile(
    r"pass[_ -]?to[_ -]?pass|metadata(?:[_ -]?only)?|co[_ -]?presence|"
    r"\bcontrol(?:led)?\b|selected[_ -]?test(?:[_ -]?only)?",
    re.IGNORECASE,
)
PLACEHOLDER_VALUES = {
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
}
FORBIDDEN_REQUEST_REJECT_REASONS = {
    "metadata_only",
    "patch_verifier_co_presence_only",
    "pass_to_pass_only",
    "controlled_or_mutation_fixture_only",
    "selected_test_observation_without_patch_effect",
}
ALLOWED_RETURN_KEYS = {
    "proof_request_id",
    "lane_ref",
    "requested_status_family",
    "language_family_label",
    "slot_statuses",
    "slot_hashes",
    "blocker_codes",
    "proof_complete",
    "anti_leak_pass",
    "training_after_return_allowed",
    "admission_after_return_allowed",
    "packaging_after_return_allowed",
    "external_repair_credit_after_return_allowed",
    "execution_performed_by_stage",
    "hydration_performed_by_stage",
    "replay_performed_by_stage",
}
VALID_LANGUAGE_LABELS = {"python", "rust", "c_cpp", "web_js_ts_html"}


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
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl_lenient(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], Counter[str]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        return rows, issues
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["schema_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["schema_invalid_not_object"] += 1
                continue
            rows.append((line_no, value))
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def normalized(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_")


def is_hash_candidate(value: str) -> bool:
    stripped = value.strip().lower()
    return bool(
        re.fullmatch(r"(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})", stripped)
    )


def is_placeholder_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    norm = normalized(value)
    if norm in PLACEHOLDER_VALUES:
        return True
    if not is_hash_candidate(value):
        return True
    compact = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return bool(compact) and len(set(compact.lower())) == 1


def public_scan(value: Any, label: str = "return_row") -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
        if FORBIDDEN_REASON_RE.search(value):
            issues.append(f"{label}:forbidden_reason_family:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(child, f"{label}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(child, f"{label}[{index}]"))
    return issues


def load_lane_specific_slots() -> tuple[dict[str, list[str]], Counter[str]]:
    issues: Counter[str] = Counter()
    pivot = read_json(PIVOT_SUMMARY)
    lanes = pivot.get("ranked_non_bears_source_lanes")
    if not isinstance(lanes, list):
        issues["stage12466_ranked_lanes_missing"] += 1
        return {}, issues
    out: dict[str, list[str]] = {}
    for lane in lanes:
        if not isinstance(lane, dict):
            issues["stage12466_ranked_lane_not_object"] += 1
            continue
        lane_ref = lane.get("lane_ref")
        slots = lane.get("required_private_proof_slots")
        if not isinstance(lane_ref, str) or not lane_ref:
            issues["stage12466_lane_ref_missing"] += 1
            continue
        if not isinstance(slots, list) or not all(isinstance(slot, str) and slot for slot in slots):
            issues[f"stage12466_lane_slots_invalid:{lane_ref}"] += 1
            continue
        out[lane_ref] = slots
    return out, issues


def load_request_items() -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not REQUEST_ITEMS.exists():
        issues["stage12467_request_items_missing"] += 1
        return rows, issues
    with REQUEST_ITEMS.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["stage12467_request_item_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["stage12467_request_item_not_object"] += 1
                continue
            required_slots = value.get("required_proof_slots")
            if not isinstance(required_slots, list) or not all(
                isinstance(slot, str) and slot for slot in required_slots
            ):
                issues["stage12467_request_item_required_slots_invalid"] += 1
            if value.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
                issues["stage12467_request_item_status_family_invalid"] += 1
            if not isinstance(value.get("proof_request_id"), str) or not value.get("proof_request_id"):
                issues["stage12467_request_item_proof_request_id_missing"] += 1
            if not isinstance(value.get("lane_ref"), str) or not value.get("lane_ref"):
                issues["stage12467_request_item_lane_ref_missing"] += 1
            forbidden_request_reasons = set(value.get("reject_if_any") or []) & FORBIDDEN_REQUEST_REJECT_REASONS
            if forbidden_request_reasons != FORBIDDEN_REQUEST_REJECT_REASONS:
                issues[f"stage12467_request_item_missing_reject_reasons_line_{line_no}"] += 1
            rows.append(value)
    return rows, issues


def required_slots_from_requests(request_items: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in request_items:
        slots = item.get("required_proof_slots")
        if not isinstance(slots, list):
            continue
        for slot in slots:
            if isinstance(slot, str) and slot and slot not in seen:
                seen.add(slot)
                ordered.append(slot)
    return ordered


def slot_status(slot_statuses: dict[str, Any], slot: str) -> Any:
    return slot_statuses.get(slot)


def validate_return_row(
    row: dict[str, Any],
    request_by_id: dict[str, dict[str, Any]],
    valid_lane_refs: set[str],
    required_slots: list[str],
    lane_specific_slots: dict[str, list[str]],
    duplicate_request_ids: set[str],
) -> tuple[bool, list[str], list[str]]:
    reasons: list[str] = []
    scan_issues = public_scan(row)

    extra_keys = sorted(set(row) - ALLOWED_RETURN_KEYS)
    if extra_keys:
        reasons.append("return_row_has_unapproved_top_level_keys")
        for key in extra_keys[:20]:
            reasons.append(f"unapproved_top_level_key:{key}")

    proof_request_id = row.get("proof_request_id")
    request_item = None
    if not isinstance(proof_request_id, str) or not proof_request_id:
        reasons.append("proof_request_id_missing")
    elif proof_request_id not in request_by_id:
        reasons.append("proof_request_id_not_in_stage12467_request_items")
    else:
        request_item = request_by_id[proof_request_id]
        if proof_request_id in duplicate_request_ids:
            reasons.append("duplicate_proof_request_id_return")

    lane_ref = row.get("lane_ref")
    if not isinstance(lane_ref, str) or not lane_ref:
        reasons.append("lane_ref_missing")
    elif lane_ref not in valid_lane_refs:
        reasons.append("lane_ref_not_in_stage12467_request_items")
    if request_item is not None and lane_ref != request_item.get("lane_ref"):
        reasons.append("lane_ref_does_not_match_proof_request_id")

    if row.get("proof_complete") is not True:
        reasons.append("proof_complete_not_true")
    if row.get("anti_leak_pass") is not True:
        reasons.append("anti_leak_pass_not_true")

    if row.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        reasons.append("requested_status_family_not_external_comparable_fail_to_pass")

    language_label = row.get("language_family_label")
    if language_label not in VALID_LANGUAGE_LABELS:
        reasons.append("language_family_label_missing_or_invalid")

    slot_statuses = row.get("slot_statuses")
    if not isinstance(slot_statuses, dict):
        reasons.append("slot_statuses_not_object")
        slot_statuses = {}

    slot_hashes = row.get("slot_hashes")
    if not isinstance(slot_hashes, dict):
        reasons.append("slot_hashes_not_object")
        slot_hashes = {}

    for slot, value in slot_statuses.items():
        if not isinstance(slot, str) or not slot:
            reasons.append("slot_status_key_invalid")
            continue
        if value != EXACT_PRESENT:
            reasons.append(f"slot_status_not_exact_present:{slot}")

    lane_required_slots = lane_specific_slots.get(str(lane_ref), [])
    combined_required_slots = list(dict.fromkeys([*required_slots, *lane_required_slots]))
    allowed_slot_keys = set(combined_required_slots)
    for key in sorted(set(slot_statuses) - allowed_slot_keys):
        reasons.append(f"unapproved_slot_status_key:{key}")
    for key in sorted(set(slot_hashes) - allowed_slot_keys):
        reasons.append(f"unapproved_slot_hash_key:{key}")
    for slot in combined_required_slots:
        if slot_status(slot_statuses, slot) != EXACT_PRESENT:
            reasons.append(f"required_slot_status_not_present:{slot}")
        if is_placeholder_hash(slot_hashes.get(slot)):
            reasons.append(f"required_slot_hash_missing_or_placeholder:{slot}")

    for slot in REQUIRED_EXPLICIT_PRESENT_SLOTS:
        if slot_status(slot_statuses, slot) != EXACT_PRESENT:
            reasons.append(f"explicit_required_slot_not_present:{slot}")

    for key, value in row.items():
        if key.endswith("_allowed") or key.endswith("_performed_by_stage"):
            if value is not False:
                reasons.append(f"{key}_not_false")

    blocker_codes = row.get("blocker_codes")
    if isinstance(blocker_codes, list) and blocker_codes:
        reasons.append("blocker_codes_present")
    elif blocker_codes is not None and not isinstance(blocker_codes, list):
        reasons.append("blocker_codes_not_list")

    if scan_issues:
        reasons.append("public_raw_or_forbidden_reason_scan_failed")

    return not reasons, reasons, scan_issues


def accepted_ref(line_no: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12468_accepted_private_return_ref_hash_only_v1",
        "return_line_hash": stable_hash({"line_no": line_no, "row": row}),
        "proof_request_id": row.get("proof_request_id"),
        "lane_ref": row.get("lane_ref"),
        "language_family_label": row.get("language_family_label"),
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "slot_statuses_hash": stable_hash(row.get("slot_statuses")),
        "slot_hashes_hash": stable_hash(row.get("slot_hashes")),
        "validator_complete": True,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
    }


def rejected_ref(line_no: int, row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "record_type": "stage12468_rejected_private_return_ref_hash_only_v1",
        "return_line_hash": stable_hash({"line_no": line_no, "row": row}),
        "proof_request_id_hash": stable_hash(row.get("proof_request_id")),
        "lane_ref_hash": stable_hash(row.get("lane_ref")),
        "reason_codes": sorted(set(reasons)),
        "validator_complete": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
    }


def build_contract(
    required_slots: list[str],
    valid_lane_refs: set[str],
    lane_specific_slots: dict[str, list[str]],
) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "stage12468_private_return_validator_contract_v1",
        "control_boundary": "hash_and_status_only_no_raw_content_no_execution_no_admission_no_training",
        "inputs": {
            "stage12467_request_items": str(REQUEST_ITEMS.relative_to(ROOT)),
            "stage12467_summary": str(REQUEST_SUMMARY.relative_to(ROOT)),
            "optional_private_return_jsonl": str(RETURN_FILE.relative_to(ROOT)),
        },
        "outputs": {
            "accepted_return_ref_index": str(ACCEPTED_INDEX.relative_to(ROOT)),
            "rejected_return_ref_index": str(REJECTED_INDEX.relative_to(ROOT)),
            "guardrail_scan": str(GUARDRAIL_OUT.relative_to(ROOT)),
            "local_summary": str(LOCAL_SUMMARY_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
        },
        "required_return_fields": [
            "proof_request_id",
            "lane_ref",
            "requested_status_family",
            "slot_statuses",
            "slot_hashes",
            "proof_complete",
            "anti_leak_pass",
        ],
        "required_status_family": EXPECTED_STATUS_FAMILY,
        "allowed_lane_refs": sorted(valid_lane_refs),
        "required_proof_slots": required_slots,
        "lane_specific_required_proof_slots": lane_specific_slots,
        "slot_acceptance_rules": [
            "every_stage12467_required_proof_slot_status_must_equal_literal_present",
            "every_stage12467_required_proof_slot_hash_must_be_24_32_40_64_hex_or_sha256_colon_64_hex_and_non_placeholder",
            "missing_not_applicable_blocked_unknown_claimed_todo_na_true_pass_and_equivalents_rejected",
            "before_fail_and_after_or_before_plus_patch_pass_slots_must_be_present",
            "anti_leak_public_rendering_pass_and_protected_overlap_audit_pass_must_be_present",
            "lane_ref_must_be_one_of_stage12467_request_item_lane_refs",
            "requested_status_family_must_be_external_comparable_fail_to_pass",
            "pass_to_pass_metadata_co_presence_control_and_selected_test_only_reasons_rejected",
            "raw_public_keys_or_raw_string_patterns_rejected",
        ],
        "non_actions": [
            "does_not_execute_tests",
            "does_not_hydrate_sources",
            "does_not_apply_patches",
            "does_not_checkout_repositories",
            "does_not_admit_rows",
            "does_not_package_rows",
            "does_not_emit_training_rows",
            "does_not_train",
            "does_not_use_network",
        ],
        "always_false_flags": {
            "training_allowed": False,
            "admission_allowed": False,
            "packaging_allowed": False,
            "execution_performed_by_stage": False,
        },
    }


def main() -> int:
    request_summary = read_json(REQUEST_SUMMARY)
    request_items, upstream_issues = load_request_items()
    lane_specific_slots, lane_slot_issues = load_lane_specific_slots()
    upstream_issues.update(lane_slot_issues)
    required_slots = required_slots_from_requests(request_items)
    request_by_id = {
        item["proof_request_id"]: item
        for item in request_items
        if isinstance(item.get("proof_request_id"), str) and item.get("proof_request_id")
    }
    valid_request_ids = set(request_by_id)
    valid_lane_refs = {
        item["lane_ref"]
        for item in request_items
        if isinstance(item.get("lane_ref"), str) and item.get("lane_ref")
    }

    if request_summary.get("requested_status_family") not in {None, EXPECTED_STATUS_FAMILY}:
        upstream_issues["stage12467_summary_status_family_invalid"] += 1
    if request_summary.get("required_proof_slots") and request_summary.get("required_proof_slots") != required_slots:
        upstream_issues["stage12467_summary_required_slots_mismatch"] += 1

    return_file_present = RETURN_FILE.exists()
    return_rows, rejected_counts = read_jsonl_lenient(RETURN_FILE)
    accepted_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []
    public_scan_issues: list[str] = []

    request_id_counts = Counter(
        row.get("proof_request_id")
        for _, row in return_rows
        if isinstance(row.get("proof_request_id"), str) and row.get("proof_request_id")
    )
    duplicate_request_ids = {request_id for request_id, count in request_id_counts.items() if count > 1}

    if not return_file_present:
        rejected_counts["private_return_file_missing"] += 1
    elif upstream_issues:
        rejected_counts.update(upstream_issues)
    else:
        for line_no, row in return_rows:
            ok, reasons, scan_issues = validate_return_row(
                row,
                request_by_id,
                valid_lane_refs,
                required_slots,
                lane_specific_slots,
                duplicate_request_ids,
            )
            public_scan_issues.extend(scan_issues)
            if ok:
                accepted_rows.append(accepted_ref(line_no, row))
            else:
                rejected_rows.append(rejected_ref(line_no, row, reasons))
                for reason in reasons:
                    rejected_counts[reason] += 1

    accepted_language_counts = Counter(
        row.get("language_family_label")
        for row in accepted_rows
        if row.get("language_family_label") in VALID_LANGUAGE_LABELS
    )
    unique_accepted_request_ids = {
        row.get("proof_request_id")
        for row in accepted_rows
        if isinstance(row.get("proof_request_id"), str)
    }
    proof_complete_count = len(unique_accepted_request_ids)
    external_credit_count = proof_complete_count
    remaining_gap = max(EXPECTED_GAP - proof_complete_count, 0)
    raw_leak_count = len(public_scan_issues)
    schema_issue_count = sum(
        count
        for reason, count in rejected_counts.items()
        if not reason.startswith("public_raw_or_forbidden_reason")
    )

    if not return_file_present:
        decision = "blocked_no_returns_external_comparable_repair_credit_zero"
    elif proof_complete_count == 0:
        decision = "blocked_no_validator_complete_private_returns_credit_zero"
    else:
        decision = "validator_complete_private_returns_hash_only_credit_counted_no_admission"

    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12468_guardrail_scan_v1",
        "scan_scope": "stage12467_private_return_rows_public_safe_status_and_hash_fields_only",
        "scan_status": "not_run_no_returns" if not return_file_present else "completed",
        "scan_passed": return_file_present and raw_leak_count == 0 and schema_issue_count == 0,
        "raw_leak_count": raw_leak_count,
        "schema_issue_count": schema_issue_count,
        "issue_hashes": [stable_hash(issue) for issue in public_scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_outputs_diffs_patches_source_text_repo_names_or_forbidden_reason_families",
    }

    contract = build_contract(required_slots, valid_lane_refs, lane_specific_slots)
    contract["allowed_return_top_level_keys"] = sorted(ALLOWED_RETURN_KEYS)
    contract["valid_language_labels"] = sorted(VALID_LANGUAGE_LABELS)
    summary = {
        "stage": STAGE,
        "record_type": "stage12468_non_bears_patch_effect_private_return_validator_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Private return validator only. Credit count is derived only from "
            "validator-complete status/hash rows; admission, packaging, execution, "
            "and training remain closed."
        ),
        "source_stage_refs": [STAGE12467],
        "return_file_present": return_file_present,
        "return_row_count": len(return_rows),
        "request_item_count": len(request_items),
        "valid_request_id_count": len(valid_request_ids),
        "valid_lane_ref_count": len(valid_lane_refs),
        "lane_specific_slot_profile_count": len(lane_specific_slots),
        "allowed_return_top_level_keys": sorted(ALLOWED_RETURN_KEYS),
        "actual_accepted_language_counts": dict(sorted(accepted_language_counts.items())),
        "proof_complete_count": proof_complete_count,
        "validator_complete_return_count": proof_complete_count,
        "accepted_return_ref_count": len(accepted_rows),
        "unique_accepted_proof_request_count": proof_complete_count,
        "duplicate_return_proof_request_id_count": len(duplicate_request_ids),
        "rejected_return_ref_count": len(rejected_rows),
        "external_comparable_repair_credit_count": external_credit_count,
        "external_fail_to_pass_admitted_count": 0,
        "remaining_external_fail_to_pass_gap": remaining_gap,
        "remaining_gap": remaining_gap,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "tests_executed_by_stage": False,
        "rows_admitted_by_stage": False,
        "model_training_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "required_proof_slots": required_slots,
        "required_explicit_present_slots": REQUIRED_EXPLICIT_PRESENT_SLOTS,
        "rejected_return_reasons": dict(sorted(rejected_counts.items())),
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": raw_leak_count,
        "schema_issue_count": schema_issue_count,
        "artifact_refs": {
            "accepted_return_ref_index": str(ACCEPTED_INDEX.relative_to(ROOT)),
            "rejected_return_ref_index": str(REJECTED_INDEX.relative_to(ROOT)),
            "validator_contract": str(CONTRACT_OUT.relative_to(ROOT)),
            "guardrail_scan": str(GUARDRAIL_OUT.relative_to(ROOT)),
            "local_summary": str(LOCAL_SUMMARY_OUT.relative_to(ROOT)),
            "summary": str(SUMMARY_OUT.relative_to(ROOT)),
        },
        "source_input_hashes": {
            "stage12467_request_items": file_hash(REQUEST_ITEMS),
            "stage12467_summary": file_hash(REQUEST_SUMMARY),
            "private_return_file": file_hash(RETURN_FILE),
        },
    }
    summary["artifact_hashes"] = {
        "accepted_return_ref_index": stable_hash(accepted_rows),
        "rejected_return_ref_index": stable_hash(rejected_rows),
        "validator_contract": stable_hash(contract),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash(
        {
            "decision": decision,
            "return_file_present": return_file_present,
            "return_row_count": len(return_rows),
            "proof_complete_count": proof_complete_count,
            "rejected_return_reasons": dict(sorted(rejected_counts.items())),
            "raw_leak_count": raw_leak_count,
            "schema_issue_count": schema_issue_count,
        }
    )

    write_json(CONTRACT_OUT, contract)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_jsonl(ACCEPTED_INDEX, accepted_rows)
    write_jsonl(REJECTED_INDEX, rejected_rows)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps({
        "stage": STAGE,
        "decision": decision,
        "return_file_present": return_file_present,
        "return_row_count": len(return_rows),
        "proof_complete_count": proof_complete_count,
        "external_comparable_repair_credit_count": external_credit_count,
        "remaining_external_fail_to_pass_gap": remaining_gap,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": raw_leak_count,
        "schema_issue_count": schema_issue_count,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
