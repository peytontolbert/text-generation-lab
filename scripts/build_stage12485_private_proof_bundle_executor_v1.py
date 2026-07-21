#!/usr/bin/env python3
"""Private proof-bundle return materializer for Stage12468.

This is the missing bridge between Stage12483 work orders and Stage12468
credit. It does not mine new candidates or claim training/admission. It reads
an optional private evidence JSONL, strips it to the Stage12468 public-safe
return schema, fail-closes on incomplete proof slots, and atomically publishes
the official Stage12468 private return file only when complete rows exist.

The optional private input path is intentionally local and absent by default:

  runs/local/artifacts/stage12483_private_proof_bundle_acquisition_work_order/
    private_proof_bundle_evidence_rows.jsonl

Rows may contain private executor-only fields, but only the allowed Stage12468
fields can be copied into the official return file.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12485_private_proof_bundle_executor_v1"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12483 = "stage12483_private_proof_bundle_acquisition_work_order"
WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_work_items_ref.jsonl"
PRIVATE_INPUT = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_evidence_rows.jsonl"

STAGE12467 = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"
REQUEST_ITEMS = ROOT / "runs/local/artifacts" / STAGE12467 / "proof_request_items.jsonl"
OFFICIAL_RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12467 / "private_proof_slot_returns.jsonl"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
VALIDATOR_CONTRACT = ROOT / "runs/local/artifacts" / STAGE12468 / "validator_contract.json"

EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
VALID_LANGUAGE_LABELS = {"python", "rust", "c_cpp", "web_js_ts_html"}
EXACT_PRESENT = "present"
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
WORK_ITEM_REF_KEYS = [
    "proof_bundle_work_item_ref_hash",
    "work_order_item_ref_hash",
]

FALSE_FLAGS = [
    "training_after_return_allowed",
    "admission_after_return_allowed",
    "packaging_after_return_allowed",
    "external_repair_credit_after_return_allowed",
    "execution_performed_by_stage",
    "hydration_performed_by_stage",
    "replay_performed_by_stage",
]
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
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b",
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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        return rows, issues
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["not_object"] += 1
                continue
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


def is_hash_candidate(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})",
            value.strip().lower(),
        )
    )


def is_placeholder_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    compact = value.strip().lower().replace("-", "_").replace("/", "_")
    if compact in PLACEHOLDER_VALUES:
        return True
    if not is_hash_candidate(value):
        return True
    alnum = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return bool(alnum) and len(set(alnum.lower())) == 1


def raw_scan(value: Any, label: str = "row") -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(raw_scan(child, f"{label}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(raw_scan(child, f"{label}[{index}]"))
    return issues


def load_requests() -> tuple[dict[str, dict[str, Any]], set[str], list[str]]:
    request_rows, _ = read_jsonl(REQUEST_ITEMS)
    request_by_id: dict[str, dict[str, Any]] = {}
    lane_refs: set[str] = set()
    required_slots: list[str] = []
    for row in request_rows:
        proof_request_id = row.get("proof_request_id")
        lane_ref = row.get("lane_ref")
        if isinstance(proof_request_id, str) and proof_request_id:
            request_by_id[proof_request_id] = row
        if isinstance(lane_ref, str) and lane_ref:
            lane_refs.add(lane_ref)
        for slot in row.get("required_proof_slots", []):
            if isinstance(slot, str) and slot not in required_slots:
                required_slots.append(slot)
    contract = read_json(VALIDATOR_CONTRACT)
    for slot in contract.get("required_proof_slots", []):
        if isinstance(slot, str) and slot not in required_slots:
            required_slots.append(slot)
    return request_by_id, lane_refs, required_slots


def sanitize_return(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: row.get(key) for key in ALLOWED_RETURN_KEYS if key in row}
    for key in WORK_ITEM_REF_KEYS:
        if key in row:
            out[key] = row.get(key)
    for key in FALSE_FLAGS:
        out[key] = False
    out.setdefault("blocker_codes", [])
    return out


def validate_return(
    row: dict[str, Any],
    request_by_id: dict[str, dict[str, Any]],
    lane_refs: set[str],
    required_slots: list[str],
    valid_work_item_refs: set[str],
) -> list[str]:
    reasons: list[str] = []
    extra_keys = set(row) - ALLOWED_RETURN_KEYS - set(WORK_ITEM_REF_KEYS)
    if extra_keys:
        reasons.append("unapproved_top_level_keys_after_sanitize")
    work_item_refs = [row.get(key) for key in WORK_ITEM_REF_KEYS if isinstance(row.get(key), str) and row.get(key)]
    if not work_item_refs:
        reasons.append("stage12483_work_item_ref_missing")
    elif not any(ref in valid_work_item_refs for ref in work_item_refs):
        reasons.append("stage12483_work_item_ref_unknown")
    proof_request_id = row.get("proof_request_id")
    if not isinstance(proof_request_id, str) or proof_request_id not in request_by_id:
        reasons.append("proof_request_id_missing_or_unknown")
    lane_ref = row.get("lane_ref")
    if not isinstance(lane_ref, str) or lane_ref not in lane_refs:
        reasons.append("lane_ref_missing_or_unknown")
    if isinstance(proof_request_id, str) and proof_request_id in request_by_id:
        if lane_ref != request_by_id[proof_request_id].get("lane_ref"):
            reasons.append("lane_ref_does_not_match_request")
    if row.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        reasons.append("requested_status_family_invalid")
    if row.get("language_family_label") not in VALID_LANGUAGE_LABELS:
        reasons.append("language_family_label_invalid")
    if row.get("proof_complete") is not True:
        reasons.append("proof_complete_not_true")
    if row.get("anti_leak_pass") is not True:
        reasons.append("anti_leak_pass_not_true")
    if row.get("blocker_codes") not in (None, []):
        reasons.append("blocker_codes_present")
    statuses = row.get("slot_statuses")
    hashes = row.get("slot_hashes")
    if not isinstance(statuses, dict):
        reasons.append("slot_statuses_not_object")
        statuses = {}
    if not isinstance(hashes, dict):
        reasons.append("slot_hashes_not_object")
        hashes = {}
    for slot in required_slots:
        if statuses.get(slot) != EXACT_PRESENT:
            reasons.append(f"slot_status_not_present:{slot}")
        if is_placeholder_hash(hashes.get(slot)):
            reasons.append(f"slot_hash_missing_or_placeholder:{slot}")
    for key in FALSE_FLAGS:
        if row.get(key) is not False:
            reasons.append(f"{key}_not_false")
    public_row = {key: value for key, value in row.items() if key in ALLOWED_RETURN_KEYS}
    if raw_scan(public_row):
        reasons.append("raw_or_private_value_scan_failed")
    return reasons


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    request_by_id, lane_refs, required_slots = load_requests()
    work_items, work_item_issues = read_jsonl(WORK_ITEMS)
    valid_work_item_refs = {
        value
        for item in work_items
        for value in (item.get("proof_bundle_work_item_ref_hash"), item.get("work_order_item_ref_hash"))
        if isinstance(value, str) and value
    }
    private_rows, private_issues = read_jsonl(PRIVATE_INPUT)
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter(work_item_issues) + Counter(private_issues)

    seen: set[str] = set()
    for index, private_row in enumerate(private_rows, 1):
        row = sanitize_return(private_row)
        reasons = validate_return(row, request_by_id, lane_refs, required_slots, valid_work_item_refs)
        proof_request_id = row.get("proof_request_id")
        if isinstance(proof_request_id, str) and proof_request_id in seen:
            reasons.append("duplicate_proof_request_id")
        if isinstance(proof_request_id, str):
            seen.add(proof_request_id)
        if reasons:
            reason_counts.update(reasons)
            rejected.append(
                {
                    "record_type": "stage12485_rejected_private_bundle_return_ref_v1",
                    "input_line_hash": stable_hash({"line": index, "row": row}),
                    "proof_request_id_hash": stable_hash(proof_request_id),
                    "reason_codes": sorted(set(reasons))[:40],
                }
            )
        else:
            accepted.append({key: value for key, value in row.items() if key in ALLOWED_RETURN_KEYS})

    official_written = False
    stale_official_return_file_removed = False
    stale_official_return_file_sha256_24 = "not_present"
    if accepted:
        tmp = OFFICIAL_RETURN_FILE.with_suffix(".jsonl.stage12485_tmp")
        write_jsonl(tmp, accepted)
        os.replace(tmp, OFFICIAL_RETURN_FILE)
        official_written = True
    elif OFFICIAL_RETURN_FILE.exists():
        stale_official_return_file_sha256_24 = file_hash(OFFICIAL_RETURN_FILE)
        OFFICIAL_RETURN_FILE.unlink()
        stale_official_return_file_removed = True

    write_jsonl(OUT / "accepted_private_return_refs.jsonl", [
        {
            "record_type": "stage12485_accepted_private_return_ref_v1",
            "return_ref_hash": stable_hash(row),
            "proof_request_id_hash": stable_hash(row.get("proof_request_id")),
            "lane_ref_hash": stable_hash(row.get("lane_ref")),
            "language_family_label_hash": stable_hash(row.get("language_family_label")),
            "validator_target_stage": STAGE12468,
        }
        for row in accepted
    ])
    write_jsonl(OUT / "rejected_private_return_refs.jsonl", rejected)

    decision = (
        "official_stage12468_private_return_file_written_rerun_stage12468"
        if official_written
        else "blocked_no_complete_private_proof_bundle_rows_no_return_file_written"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12485_private_proof_bundle_executor_v1_summary",
        "decision": decision,
        "source_stage_refs": [STAGE12483, STAGE12467, STAGE12468],
        "private_input_present": PRIVATE_INPUT.exists(),
        "private_input_row_count": len(private_rows),
        "stage12483_work_item_count": len(work_items),
        "stage12468_required_slot_count": len(required_slots),
        "stage12483_valid_work_item_ref_count": len(valid_work_item_refs),
        "accepted_return_candidate_count": len(accepted),
        "rejected_return_candidate_count": len(rejected),
        "official_stage12468_return_file_written": official_written,
        "official_stage12468_return_file_row_count": len(accepted) if official_written else 0,
        "official_stage12468_return_file_sha256_24": file_hash(OFFICIAL_RETURN_FILE) if official_written else "not_written",
        "stale_official_return_file_removed": stale_official_return_file_removed,
        "stale_official_return_file_sha256_24": stale_official_return_file_sha256_24,
        "blocked_condition_count": 0 if official_written else 1,
        "blocked_conditions": [] if official_written else ["complete_private_proof_bundle_input_missing_or_invalid"],
        "reject_reason_counts": dict(reason_counts),
        "raw_leak_count": 0,
        "training_rows_emitted": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "external_repair_credit_count": 0,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "next_action": "rerun_stage12468" if official_written else "fill_private_proof_bundle_evidence_rows_then_rerun_stage12485",
    }
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)
    write_json(OUT / "private_input_contract.json", {
        "private_input_path": str(PRIVATE_INPUT.relative_to(ROOT)),
        "official_output_path": str(OFFICIAL_RETURN_FILE.relative_to(ROOT)),
        "allowed_return_keys": sorted(ALLOWED_RETURN_KEYS),
        "private_only_work_item_ref_keys_required": WORK_ITEM_REF_KEYS,
        "required_proof_slots": required_slots,
        "publish_rule": "official return file is atomically written only when at least one row passes local prevalidation",
    })
    (OUT / "PRIVATE_PROOF_BUNDLE_EXECUTOR_V1_STAGE12485.md").write_text(
        "# Stage12485 Private Proof Bundle Executor V1\n\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
