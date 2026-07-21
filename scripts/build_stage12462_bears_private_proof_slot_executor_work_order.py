#!/usr/bin/env python3
"""Build Stage12462 fail-closed Bears private proof-slot executor work order.

This stage converts Stage12460 public-safe request items into a future private
executor work order. It does not checkout repositories, run tests, train, admit
rows, package rows, or emit proof/training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12462_bears_private_proof_slot_executor_work_order"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12460 = "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request"
STAGE12461 = "stage12461_external_patch_effect_return_validator"
STAGE12460_OUT = ROOT / "runs/local/artifacts" / STAGE12460
STAGE12460_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12460}.json"
REQUEST_ITEMS = STAGE12460_OUT / "private_proof_slot_request_items.jsonl"
RETURN_SCHEMA = STAGE12460_OUT / "private_proof_slot_return_schema.json"
STAGE12461_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12461}.json"

MANIFEST_OUT = OUT_DIR / "work_order_manifest.json"
WORK_ITEMS_OUT = OUT_DIR / "executor_work_items.jsonl"
ARTIFACT_SUMMARY_OUT = OUT_DIR / "summary.json"

PRIMARY_LANE = "bears_failing_passing_java_side_lane"
EXPECTED_GAP = 15
MAX_REQUESTS_PER_SHARD = 5
DECLARED_RETURN_PATH = (
    "runs/local/artifacts/"
    "stage12460_external_comparable_patch_effect_private_proof_slot_materialization_request/"
    "private_proof_slot_returns.jsonl"
)

ZERO_FALSE_FLAGS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "external_repair_credit_after_execution_allowed": False,
}

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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


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


def stage12461_zero_credit_fail_closed(summary: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    required_false = [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
        "tests_executed_by_stage",
        "rows_admitted_by_stage",
        "model_training_performed_by_stage",
    ]
    required_zero = [
        "accepted_return_ref_count",
        "admitted_count",
        "admitted_external_comparable_repair_credit_count",
        "emitted_training_rows",
        "sealed_eval_rows",
        "proof_complete_count",
        "return_row_count",
    ]
    if summary.get("stage") != STAGE12461:
        blockers.append("stage12461_unexpected_stage")
    if summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12461_guardrail_scan_not_passed")
    for key in required_false:
        if summary.get(key) is not False:
            blockers.append(f"stage12461_{key}_not_false")
    for key in required_zero:
        if summary.get(key) != 0:
            blockers.append(f"stage12461_{key}_not_zero")
    if not str(summary.get("decision") or "").startswith("blocked_"):
        blockers.append("stage12461_decision_not_blocked_fail_closed")
    return not blockers, blockers


def derive_required_slots(stage12460_summary: dict[str, Any], stage12461_summary: dict[str, Any]) -> list[str]:
    slots: list[str] = []
    for source in (stage12460_summary, stage12461_summary):
        for slot in source.get("required_return_slots") or []:
            if isinstance(slot, str) and slot not in slots:
                slots.append(slot)
    return slots


def validate_stage12460(summary: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if summary.get("stage") != STAGE12460:
        blockers.append("stage12460_unexpected_stage")
    if summary.get("request_count") != len(rows):
        blockers.append("stage12460_request_count_mismatch")
    if summary.get("primary_lane") != PRIMARY_LANE:
        blockers.append("stage12460_primary_lane_not_bears_java_side_lane")
    if summary.get("primary_lane_request_count") != len(rows):
        blockers.append("stage12460_primary_lane_count_mismatch")
    for key in ["training_allowed", "admission_allowed", "execution_performed_by_stage"]:
        if summary.get(key) is not False:
            blockers.append(f"stage12460_{key}_not_false")
    if summary.get("expected_credit_now") != 0:
        blockers.append("stage12460_expected_credit_now_not_zero")
    if summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12460_guardrail_scan_not_passed")
    return blockers


def build_work_item(
    row: dict[str, Any],
    required_slots: list[str],
    return_schema_ref: str,
) -> dict[str, Any]:
    candidate_ref_hash = str(row.get("candidate_ref_hash") or "")
    source_lane_id = str(row.get("source_lane_id") or "")
    priority_rank = row.get("priority_rank")
    return {
        "record_type": "stage12462_executor_work_item_hash_only_v1",
        "work_order_item_ref_hash": stable_hash(
            {
                "candidate_ref_hash": candidate_ref_hash,
                "priority_rank": priority_rank,
                "source_lane_id": source_lane_id,
            }
        ),
        "request_kind": row.get("request_kind"),
        "source_lane_id": source_lane_id,
        "source_lane_id_hash": stable_hash(source_lane_id),
        "language_bucket": str(
            row.get("language_bucket")
            or "single_jvm_java_only_not_multilingual_coverage"
        ),
        "candidate_ref_hash": candidate_ref_hash,
        "priority_rank": priority_rank,
        "required_return_slots": required_slots,
        "return_schema_ref": return_schema_ref,
        "expected_return_path": DECLARED_RETURN_PATH,
        "public_return_policy_ref": "stage12460_hashes_counts_normalized_statuses_and_blocker_codes_only",
        "multilingual_coverage_credit": False,
        "expected_credit_now": 0,
        "external_repair_credit_after_execution_allowed": False,
        "training_after_execution_allowed": False,
        "admission_after_execution_allowed": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
    }


def build_shard_manifests(work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shard_manifests: list[dict[str, Any]] = []
    for shard_index, start in enumerate(range(0, len(work_items), MAX_REQUESTS_PER_SHARD), 1):
        shard_items = work_items[start : start + MAX_REQUESTS_PER_SHARD]
        shard_name = f"executor_work_items_shard_{shard_index:02d}.json"
        shard_path = OUT_DIR / shard_name
        shard_manifest = {
            "record_type": "stage12462_executor_work_order_shard_manifest_v1",
            "shard_id": f"stage12462_bears_private_executor_shard_{shard_index:02d}",
            "request_count": len(shard_items),
            "max_requests_per_shard": MAX_REQUESTS_PER_SHARD,
            "work_order_item_ref_hashes": [
                item["work_order_item_ref_hash"] for item in shard_items
            ],
            "expected_return_path": DECLARED_RETURN_PATH,
            "training_allowed": False,
            "admission_allowed": False,
            "packaging_allowed": False,
            "execution_performed_by_stage": False,
        }
        write_json(shard_path, shard_manifest)
        shard_manifests.append(
            {
                "shard_ref": shard_manifest["shard_id"],
                "shard_manifest_ref": f"stage12462_{shard_name}",
                "request_count": len(shard_items),
                "shard_manifest_hash": stable_hash(shard_manifest),
            }
        )
    return shard_manifests


def main() -> int:
    stage12460_summary = read_json(STAGE12460_SUMMARY)
    stage12461_summary = read_json(STAGE12461_SUMMARY)
    return_schema = read_json(RETURN_SCHEMA)
    request_rows = read_jsonl(REQUEST_ITEMS)

    blockers = validate_stage12460(stage12460_summary, request_rows)
    stage12461_ok, stage12461_blockers = stage12461_zero_credit_fail_closed(stage12461_summary)
    if not stage12461_ok:
        blockers.extend(stage12461_blockers)

    required_slots = derive_required_slots(stage12460_summary, stage12461_summary)
    return_schema_ref = str(
        stage12460_summary.get("return_schema_ref")
        or return_schema.get("schema_id")
        or "stage12460_private_proof_slot_return_schema_v1"
    )
    work_items = [
        build_work_item(row, required_slots, return_schema_ref)
        for row in sorted(request_rows, key=lambda item: item.get("priority_rank") or 0)
    ]
    shard_refs = build_shard_manifests(work_items)

    manifest = {
        "stage": STAGE,
        "record_type": "stage12462_bears_private_proof_slot_executor_work_order_manifest_v1",
        "decision": (
            "fail_closed_executor_work_order_ready_zero_credit"
            if not blockers
            else "blocked_executor_work_order_zero_credit"
        ),
        "claim_boundary": (
            "Executor work order only. Stage12462 performs no checkouts, tests, patch "
            "application, private execution, proof-row emission, admission, packaging, or training."
        ),
        "request_count": len(work_items),
        "stage12460_request_count": stage12460_summary.get("request_count"),
        "request_count_matches_stage12460": len(work_items) == stage12460_summary.get("request_count"),
        "request_count_bucket": count_bucket(len(work_items)),
        "primary_lane": PRIMARY_LANE,
        "primary_lane_request_count": len(work_items),
        "primary_lane_request_count_bucket": count_bucket(len(work_items)),
        "multilingual_coverage_credit": False,
        "expected_credit_now": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "external_repair_credit_after_execution_allowed": False,
        "training_after_execution_allowed": False,
        "admission_after_execution_allowed": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "required_return_slots": required_slots,
        "required_return_slots_ref": "stage12462_bears_required_return_slots_for_stage12461_v1",
        "return_schema_ref": return_schema_ref,
        "expected_return_path": DECLARED_RETURN_PATH,
        "executor_contract": {
            "private_executor_may_inspect_raw_materials": True,
            "stage12462_may_not_inspect_raw_materials": True,
            "public_return_must_exclude_raw_repo_names_paths_urls_commands_outputs_diffs_and_source_text": True,
            "write_return_rows_to_expected_return_path": True,
            "stage12461_or_next_validator_must_consume_expected_return_path": True,
            "proof_complete_must_fail_closed_unless_all_required_slots_are_present": True,
            "credit_training_admission_and_packaging_flags_must_remain_false": True,
        },
        "artifact_refs": {
            "work_order_manifest": "stage12462_work_order_manifest_json",
            "executor_work_items": "stage12462_executor_work_items_jsonl",
            "summary": "stage12462_summary_json",
            "shard_manifests": [row["shard_manifest_ref"] for row in shard_refs],
        },
        "shard_policy": {
            "enabled": True,
            "max_requests_per_shard": MAX_REQUESTS_PER_SHARD,
            "shard_count": len(shard_refs),
            "shards": shard_refs,
        },
        "stage12461_zero_credit_fail_closed": stage12461_ok,
        "blockers": blockers,
        "source_input_hashes": {
            "stage12460_summary": file_hash(STAGE12460_SUMMARY),
            "stage12460_request_items": file_hash(REQUEST_ITEMS),
            "stage12460_return_schema": file_hash(RETURN_SCHEMA),
            "stage12461_summary": file_hash(STAGE12461_SUMMARY),
        },
    }
    manifest["guardrail_scan"] = {
        "scan_scope": "stage12462_public_executor_work_order_manifest_items_and_shards",
        "scan_passed": True,
        "raw_leak_count": 0,
        "issues": [],
    }
    manifest["guardrail_scan_passed"] = True
    manifest["raw_leak_count"] = 0
    manifest["work_order_manifest_hash"] = stable_hash(
        {key: value for key, value in manifest.items() if key != "work_order_manifest_hash"}
    )

    public_payload = {
        "manifest": manifest,
        "work_items": work_items,
        "shard_refs": shard_refs,
    }
    issues = scan_public("stage12462", public_payload)
    if issues:
        manifest["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        manifest["guardrail_scan"] = {
            "scan_scope": "stage12462_public_executor_work_order_manifest_items_and_shards",
            "scan_passed": False,
            "raw_leak_count": len(issues),
            "issue_hashes": [stable_hash(issue) for issue in issues[:50]],
        }
        manifest["guardrail_scan_passed"] = False
        manifest["raw_leak_count"] = len(issues)
        blockers.append("stage12462_public_guardrail_scan_failed")

    summary = dict(manifest)
    summary["record_type"] = "stage12462_bears_private_proof_slot_executor_work_order_summary_v1"

    write_jsonl(WORK_ITEMS_OUT, work_items)
    write_json(MANIFEST_OUT, manifest)
    write_json(ARTIFACT_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(SUMMARY_OUT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
