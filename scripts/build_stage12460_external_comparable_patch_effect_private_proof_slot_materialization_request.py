#!/usr/bin/env python3
"""Build Stage12460 private proof-slot materialization request.

This stage creates public-safe work orders only. It does not run checkouts,
apply patches, execute verifiers, admit rows, or emit model training rows.
Candidate identity is represented only by salted hashes.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

SOURCE_PREFLIGHT = (
    ROOT / "runs/summaries/stage12459_external_comparable_patch_effect_source_preflight.json"
)
BEARS_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "bears_failing_passing_candidates.jsonl"
)
OPEN_SWE_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "open_swe_priority_capped_trace_support_candidates.jsonl"
)

PRIMARY_LANE_ID = "bears_failing_passing_java_side_lane"
SECONDARY_LANE_ID = "open_swe_authoritative_replay_quarantined_secondary_lane"
EXPECTED_GAP = 15

REQUIRED_RETURN_SLOTS = [
    "buggy_checkout_content_availability",
    "fixed_checkout_content_availability",
    "buggy_verifier_fail",
    "fixed_or_before_plus_patch_verifier_pass",
    "exact_same_verifier_identity",
    "patch_diff_apply_lineage",
    "verifier_relevance",
    "same_source_lineage",
    "source_test_hashes",
    "anti_leak_pass",
]

SECONDARY_REQUIRED_RETURN_SLOTS = [
    "authoritative_before_state_availability",
    "authoritative_after_or_patch_state_availability",
    "before_verifier_fail",
    "after_or_before_plus_patch_verifier_pass",
    "exact_same_verifier_identity",
    "patch_apply_or_trace_lineage",
    "verifier_relevance",
    "same_source_lineage",
    "source_test_hashes",
    "anti_leak_pass",
    "secondary_quarantine_reason",
]

BLOCKER_CODES = [
    "missing_buggy_checkout_content",
    "missing_fixed_checkout_content",
    "buggy_verifier_not_fail",
    "fixed_or_patched_verifier_not_pass",
    "verifier_identity_mismatch",
    "patch_lineage_missing_or_incomparable",
    "verifier_not_relevant_to_patch",
    "same_source_lineage_missing",
    "source_test_hashes_missing",
    "anti_leak_failed",
    "raw_content_detected",
    "schema_invalid",
    "private_evidence_incomplete",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|command output|terminal output|git clone|"
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
    "patch_body",
    "raw_text",
    "source_text",
}
KEY_ALLOW_RE = re.compile(r"(hash|hashes|policy|slot|slots|blocker|scan)", re.IGNORECASE)


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
    if count <= 249:
        return "75-249"
    return "250-plus"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must be a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path.name}:{line_no} must be a JSON object")
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


def int_value(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    return default


def source_ref_hash(row: dict[str, Any], lane_id: str) -> str:
    private_identity = {
        "lane_id": lane_id,
        "candidate_id": row.get("candidate_id"),
        "source_record_ref": row.get("source_record_ref"),
        "source_adapter": row.get("source_adapter"),
        "buggy_build_id": row.get("buggy_build_id"),
        "fixer_build_id": row.get("fixer_build_id"),
        "buggy_commit_sha": row.get("buggy_commit_sha"),
        "fixer_commit_sha": row.get("fixer_commit_sha"),
        "patch_diff_hash": row.get("patch_diff_hash"),
        "selected_test_hashes": row.get("selected_test_hashes"),
        "seed_path_hashes": row.get("seed_path_hashes"),
    }
    return stable_hash(private_identity)


def request_language_bucket(lane_id: str) -> str:
    if "bears" in lane_id:
        return "single_jvm_java_only_not_multilingual_coverage"
    if "open_swe" in lane_id:
        return "quarantined_multilingual_trace_support_not_repair_credit"
    return "unknown_or_not_public"


def request_item(row: dict[str, Any], lane_id: str, slots: list[str], rank: int) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "record_type": "private_proof_slot_materialization_request_item_v1",
        "request_kind": "private_proof_slot_materialization_request",
        "source_lane_id": lane_id,
        "language_bucket": request_language_bucket(lane_id),
        "priority_rank": rank,
        "candidate_ref_hash": source_ref_hash(row, lane_id),
        "required_return_slots": slots,
        "return_schema_ref": "stage12460_private_proof_slot_return_schema_v1",
        "public_return_policy": "hashes_counts_normalized_statuses_and_blocker_codes_only",
        "external_repair_credit_after_return_allowed": False,
        "training_after_return_allowed": False,
        "admission_after_return_allowed": False,
    }


def return_schema() -> dict[str, Any]:
    return {
        "schema_id": "stage12460_private_proof_slot_return_schema_v1",
        "record_type": "private_proof_slot_return_schema_fail_closed_v1",
        "return_policy": "private_executor_may_inspect_raw_materials_but_public_return_must_not_include_them",
        "raw_content_fields_allowed_in_public_return": False,
        "required_public_fields": [
            "request_kind",
            "source_lane_id",
            "candidate_ref_hash",
            "proof_complete",
            "slot_statuses",
            "slot_hashes",
            "blocker_codes",
            "anti_leak_pass",
            "external_repair_credit_after_return_allowed",
            "training_after_return_allowed",
            "admission_after_return_allowed",
        ],
        "slot_status_allowed_values": ["present", "missing", "incomparable", "failed"],
        "fail_closed_rules": [
            "proof_complete_must_be_false_unless_all_required_slots_are_present",
            "any_blocker_code_forces_proof_complete_false",
            "any_raw_content_in_public_return_forces_anti_leak_pass_false",
            "any_verifier_identity_mismatch_blocks_candidate",
            "any_before_status_other_than_fail_blocks_candidate",
            "any_after_or_patched_status_other_than_pass_blocks_candidate",
            "credit_training_and_admission_flags_must_remain_false",
        ],
        "blocker_codes": BLOCKER_CODES,
    }


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


def validate_source_preflight(summary: dict[str, Any]) -> None:
    if summary.get("stage") != "stage12459_external_comparable_patch_effect_source_preflight":
        raise SystemExit("fail_closed: unexpected source preflight stage")
    if summary.get("training_allowed") is not False:
        raise SystemExit("fail_closed: upstream training flag is not false")
    if summary.get("admission_allowed") is not False:
        raise SystemExit("fail_closed: upstream admission flag is not false")
    if int_value(summary.get("external_comparable_repair_credit_count")) != 0:
        raise SystemExit("fail_closed: upstream external repair credit is nonzero")
    if int_value(summary.get("external_fail_to_pass_remaining_floor_gap")) != EXPECTED_GAP:
        raise SystemExit("fail_closed: upstream remaining gap is not 15")
    if summary.get("guardrail_scan_passed") is not True:
        raise SystemExit("fail_closed: upstream public guardrail scan did not pass")


def build_summary(
    bears_items: list[dict[str, Any]],
    secondary_items: list[dict[str, Any]],
    bears_count: int,
    open_swe_count: int,
) -> dict[str, Any]:
    request_count = len(bears_items) + len(secondary_items)
    bears_note = (
        "Bears has 19 candidates here, so this is a Java-only side-lane and must not be "
        "claimed as multilingual coverage; it remains useful for the external repair floor "
        "only if enough private returns are proof-complete."
        if bears_count == 19
        else "Bears lane is primary but has no multilingual coverage claim."
    )
    return {
        "stage": STAGE,
        "record_type": "external_comparable_patch_effect_private_proof_slot_materialization_request_summary_v1",
        "decision": "request_only_no_execution_no_admission_no_training",
        "claim_boundary": (
            "Public-safe private proof-slot materialization request only. No checkout, verifier, "
            "patch application, row admission, or model training is performed by this stage."
        ),
        "request_count": request_count,
        "request_count_bucket": count_bucket(request_count),
        "primary_lane": PRIMARY_LANE_ID,
        "primary_lane_request_count": len(bears_items),
        "primary_lane_request_count_bucket": count_bucket(len(bears_items)),
        "secondary_lane": SECONDARY_LANE_ID,
        "secondary_lane_count": len(secondary_items),
        "secondary_lane_available_count_bucket": count_bucket(open_swe_count),
        "expected_credit_now": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "training_allowed": False,
        "admission_allowed": False,
        "execution_performed_by_stage": False,
        "external_repair_credit_after_return_allowed": False,
        "training_after_return_allowed": False,
        "admission_after_return_allowed": False,
        "emitted_training_rows": 0,
        "bears_coverage_note": bears_note,
        "open_swe_secondary_policy": (
            "Secondary quarantined replay support only; not needed for the primary Bears-first "
            "floor request and not eligible for current credit, training, or admission."
        ),
        "required_return_slots_ref": "stage12460_bears_required_return_slots_v1",
        "required_return_slots": REQUIRED_RETURN_SLOTS,
        "return_schema_ref": "stage12460_private_proof_slot_return_schema_v1",
        "artifact_refs": {
            "request_items": "stage12460_private_proof_slot_request_items_jsonl",
            "return_schema": "stage12460_private_proof_slot_return_schema_json",
            "summary": "stage12460_summary_json",
        },
        "source_input_hashes": {
            "stage12459_source_preflight": file_hash(SOURCE_PREFLIGHT),
            "stage12327_bears_failing_passing_candidates": file_hash(BEARS_CANDIDATES),
            "stage12327_open_swe_priority_candidates": file_hash(OPEN_SWE_CANDIDATES),
        },
    }


def main() -> None:
    source_preflight = read_json(SOURCE_PREFLIGHT)
    validate_source_preflight(source_preflight)

    bears_rows = read_jsonl(BEARS_CANDIDATES)
    open_swe_rows = read_jsonl(OPEN_SWE_CANDIDATES) if OPEN_SWE_CANDIDATES.exists() else []

    bears_items = [
        request_item(row, PRIMARY_LANE_ID, REQUIRED_RETURN_SLOTS, rank)
        for rank, row in enumerate(bears_rows, 1)
    ]
    # Bears has enough candidates to cover the current 15-row floor if proof-complete.
    # Keep Open-SWE available only as a quarantined secondary lane, without work-order emission.
    secondary_items: list[dict[str, Any]] = []

    schema = return_schema()
    summary = build_summary(bears_items, secondary_items, len(bears_rows), len(open_swe_rows))
    all_public = {
        "summary": summary,
        "request_items": bears_items + secondary_items,
        "return_schema": schema,
    }
    issues = scan_public("stage12460", all_public)
    summary["guardrail_scan"] = {
        "scan_scope": "stage12460_public_request_items_summary_and_return_schema",
        "scan_passed": not issues,
        "raw_leak_count": len(issues),
        "issues": issues,
    }
    summary["guardrail_scan_passed"] = not issues
    summary["raw_leak_count"] = len(issues)
    summary["summary_hash"] = stable_hash(
        {key: value for key, value in summary.items() if key != "summary_hash"}
    )

    final_public = {
        "summary": summary,
        "request_items": bears_items + secondary_items,
        "return_schema": schema,
    }
    final_issues = scan_public("stage12460", final_public)
    if final_issues:
        summary["guardrail_scan"] = {
            "scan_scope": "stage12460_public_request_items_summary_and_return_schema",
            "scan_passed": False,
            "raw_leak_count": len(final_issues),
            "issues": final_issues,
        }
        summary["guardrail_scan_passed"] = False
        summary["raw_leak_count"] = len(final_issues)
        write_json(OUT_DIR / "summary.json", summary)
        write_json(SUMMARY_OUT, summary)
        raise SystemExit("fail_closed: public guardrail scan detected leakage")

    write_jsonl(OUT_DIR / "private_proof_slot_request_items.jsonl", bears_items + secondary_items)
    write_json(OUT_DIR / "private_proof_slot_return_schema.json", schema)
    write_json(OUT_DIR / "summary.json", summary)
    write_json(SUMMARY_OUT, summary)


if __name__ == "__main__":
    main()
