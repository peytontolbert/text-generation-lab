#!/usr/bin/env python3
"""Build Stage12470 non-Bears private return locator preflight.

This stage checks whether Stage12469 public work items contain enough
hash-only locator material for a private executor to act. It is fail-closed:
it does not execute, hydrate, replay, use network, train, admit, or package.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12470_non_bears_private_return_locator_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12466 = "stage12466_external_repair_source_pivot_control"
STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12469 = "stage12469_non_bears_private_proof_return_work_order"

STAGE12466_OUT = ROOT / "runs/local/artifacts" / STAGE12466
STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
STAGE12469_OUT = ROOT / "runs/local/artifacts" / STAGE12469

RANKED_LANES_IN = STAGE12466_OUT / "ranked_non_bears_source_lanes.jsonl"
STAGE12466_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12466}.json"
VALIDATOR_CONTRACT_IN = STAGE12468_OUT / "validator_contract.json"
STAGE12468_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12468}.json"
WORK_ITEMS_IN = STAGE12469_OUT / "private_return_work_items.jsonl"
STAGE12469_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12469}.json"

LOCATOR_REQUIREMENTS_OUT = OUT_DIR / "locator_requirement_records.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
REQUIRED_LOCATOR_FIELDS = [
    "source_adapter_candidate_ref_hash",
    "private_locator_ref_hash",
    "source_root_label_hash",
    "lane_candidate_family_hash",
    "private_execution_context_ref_hash",
]
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
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label)",
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
PLACEHOLDER_VALUES = {
    "",
    "blocked",
    "claim",
    "claimed",
    "claimed_only",
    "equivalent",
    "false",
    "missing",
    "n_a",
    "na",
    "no",
    "none",
    "not_applicable",
    "null",
    "ok",
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


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        issues["input_jsonl_missing"] += 1
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
            value["_stage12470_input_line_index"] = line_no
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


def unique_ordered(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str) and value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def normalized(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_")


def is_hash_candidate(value: str) -> bool:
    stripped = value.strip().lower()
    return bool(
        re.fullmatch(
            r"(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|"
            r"sha256:[0-9a-f]{64})",
            stripped,
        )
    )


def is_public_locator_value_present(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    norm = normalized(value)
    if norm in PLACEHOLDER_VALUES:
        return False
    if not is_hash_candidate(value):
        return False
    compact = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return bool(compact) and len(set(compact.lower())) > 1


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


def lane_map(ranked_lanes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for lane in ranked_lanes:
        lane_ref = lane.get("lane_ref")
        if isinstance(lane_ref, str) and lane_ref:
            out[lane_ref] = lane
    return out


def item_required_slots(
    item: dict[str, Any],
    validator_contract: dict[str, Any],
    lane: dict[str, Any] | None,
) -> tuple[list[str], list[str], list[str]]:
    contract_common = validator_contract.get("required_proof_slots")
    common = unique_ordered(contract_common if isinstance(contract_common, list) else [])
    item_common = item.get("required_common_slots")
    if isinstance(item_common, list):
        common = unique_ordered([*common, *item_common])
    item_combined = item.get("required_combined_slots")
    if isinstance(item_combined, list):
        combined_hint = unique_ordered(item_combined)
    else:
        combined_hint = []

    lane_slots: list[str] = []
    if lane:
        lane_raw = lane.get("required_private_proof_slots")
        if isinstance(lane_raw, list):
            lane_slots = unique_ordered(lane_raw)
    item_lane_slots = item.get("required_lane_specific_slots")
    if isinstance(item_lane_slots, list):
        lane_slots = unique_ordered([*lane_slots, *item_lane_slots])

    combined = unique_ordered([*common, *lane_slots, *combined_hint])
    return common, lane_slots, combined


def build_locator_record(
    item: dict[str, Any],
    index: int,
    validator_contract: dict[str, Any],
    lanes_by_ref: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    lane_ref = str(item.get("lane_ref") or "")
    lane = lanes_by_ref.get(lane_ref)
    common_slots, lane_slots, combined_slots = item_required_slots(
        item, validator_contract, lane
    )

    locator_presence = {
        field: is_public_locator_value_present(item.get(field))
        for field in REQUIRED_LOCATOR_FIELDS
    }
    missing_locator_fields = [
        field for field, present in locator_presence.items() if not present
    ]
    blocker_reasons = [
        f"missing_public_locator_field:{field}" for field in missing_locator_fields
    ]
    if lane is None:
        blocker_reasons.append("lane_ref_not_found_in_stage12466_ranked_lanes")
    if item.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        blocker_reasons.append("requested_status_family_not_external_comparable_fail_to_pass")
    if item.get("external_comparable_repair_credit_count") != 0:
        blocker_reasons.append("upstream_work_item_credit_not_zero")

    proof_request_ref_hash = item.get("proof_request_ref_hash")
    if not is_public_locator_value_present(proof_request_ref_hash):
        proof_request_ref_hash = stable_hash(
            {
                "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
                "line_index": index,
            }
        )

    return {
        "record_type": "stage12470_public_safe_locator_requirement_v1",
        "work_order_item_ref_hash": item.get("work_order_item_ref_hash")
        or stable_hash({"line_index": index, "item": item}),
        "proof_request_id_hash": proof_request_ref_hash,
        "lane_ref": lane_ref,
        "lane_ref_hash": item.get("lane_ref_hash") or stable_hash(lane_ref),
        "language_priority_hint": item.get("language_priority_hint"),
        "language_priority_hint_hash": item.get("language_priority_hint_hash")
        or stable_hash(item.get("language_priority_hint")),
        "candidate_language_verified": bool(item.get("candidate_language_verified")),
        "language_family_label": item.get("language_family_label"),
        "required_candidate_locator_fields": REQUIRED_LOCATOR_FIELDS,
        "candidate_locator_field_presence": locator_presence,
        "candidate_locator_present_count": sum(1 for present in locator_presence.values() if present),
        "candidate_locator_missing_count": len(missing_locator_fields),
        "required_proof_slots_count": len(combined_slots),
        "lane_specific_slot_count": len(lane_slots),
        "required_common_slots_count": len(common_slots),
        "actionability_status": (
            "blocked_missing_private_locator_fields"
            if blocker_reasons
            else "locator_requirements_public_artifact_present"
        ),
        "blocker_reasons": sorted(set(blocker_reasons)),
        "private_executor_requirement": (
            "private_locator_index_must_supply_all_required_candidate_locator_hash_fields"
        ),
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "network_performed_by_stage": False,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
    }


def input_blockers(
    work_items: list[dict[str, Any]],
    work_item_issues: Counter[str],
    ranked_lanes: list[dict[str, Any]],
    lane_issues: Counter[str],
    validator_contract: dict[str, Any],
    stage12466_summary: dict[str, Any],
    stage12468_summary: dict[str, Any],
    stage12469_summary: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    blockers.extend(f"stage12469_work_items_{key}" for key in work_item_issues)
    blockers.extend(f"stage12466_ranked_lanes_{key}" for key in lane_issues)
    if not work_items:
        blockers.append("stage12469_work_items_empty")
    if not ranked_lanes:
        blockers.append("stage12466_ranked_lanes_empty")
    if validator_contract.get("stage") != STAGE12468:
        blockers.append("stage12468_validator_contract_unexpected_stage")
    if validator_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12468_validator_contract_status_family_invalid")
    if stage12466_summary.get("stage") != STAGE12466:
        blockers.append("stage12466_summary_unexpected_stage")
    if stage12468_summary.get("stage") != STAGE12468:
        blockers.append("stage12468_summary_unexpected_stage")
    if stage12469_summary.get("stage") != STAGE12469:
        blockers.append("stage12469_summary_unexpected_stage")
    if stage12469_summary.get("request_count") != len(work_items):
        blockers.append("stage12469_work_item_count_mismatch")
    for key, expected in FALSE_GUARDS.items():
        if key == "network_performed_by_stage":
            continue
        if stage12469_summary.get(key) is not expected:
            blockers.append(f"stage12469_{key}_not_false")
    for key, expected in ZERO_GUARDS.items():
        if stage12469_summary.get(key) != expected:
            blockers.append(f"stage12469_{key}_not_{expected}")
    if stage12469_summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12469_guardrail_scan_not_passed")
    if stage12469_summary.get("raw_leak_count") != 0:
        blockers.append("stage12469_raw_leak_count_not_zero")
    return sorted(set(blockers))


def summarize_blocker_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        for reason in record.get("blocker_reasons") or []:
            if isinstance(reason, str):
                counts[reason] += 1
    return dict(sorted(counts.items()))


def language_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for record in records:
        label = record.get("language_priority_hint")
        if isinstance(label, str) and label:
            counts[label] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    work_items, work_item_issues = read_jsonl(WORK_ITEMS_IN)
    ranked_lanes, lane_issues = read_jsonl(RANKED_LANES_IN)
    validator_contract = read_json(VALIDATOR_CONTRACT_IN)
    stage12466_summary = read_json(STAGE12466_SUMMARY)
    stage12468_summary = read_json(STAGE12468_SUMMARY)
    stage12469_summary = read_json(STAGE12469_SUMMARY)

    lanes_by_ref = lane_map(ranked_lanes)
    records = [
        build_locator_record(item, index, validator_contract, lanes_by_ref)
        for index, item in enumerate(work_items, 1)
    ]

    upstream_blockers = input_blockers(
        work_items,
        work_item_issues,
        ranked_lanes,
        lane_issues,
        validator_contract,
        stage12466_summary,
        stage12468_summary,
        stage12469_summary,
    )
    actionable_count = sum(
        1 for record in records if not record.get("blocker_reasons")
    )
    blocked_count = len(records) - actionable_count
    missing_counts = summarize_blocker_counts(records)
    stage_blockers = sorted(
        set(
            [
                *upstream_blockers,
                *missing_counts,
            ]
        )
    )
    if blocked_count:
        stage_blockers.append("stage12470_private_locator_index_missing_for_work_items")

    summary = {
        "stage": STAGE,
        "record_type": "stage12470_non_bears_private_return_locator_preflight_summary_v1",
        "decision": (
            "blocked_no_actionable_private_locator_requirements_zero_credit"
            if stage_blockers or actionable_count == 0
            else "locator_preflight_ready_zero_credit_no_execution"
        ),
        "claim_boundary": (
            "Locator preflight only. Stage12470 emits public-safe locator "
            "requirements and performs no execution, hydration, replay, network "
            "access, training, admission, or packaging."
        ),
        "input_stage_refs": [STAGE12469, STAGE12468, STAGE12466],
        "work_item_count": len(work_items),
        "locator_requirement_record_count": len(records),
        "locator_requirement_record_count_bucket": count_bucket(len(records)),
        "actionable_locator_requirement_count": actionable_count,
        "blocked_locator_requirement_count": blocked_count,
        "required_candidate_locator_fields": REQUIRED_LOCATOR_FIELDS,
        "required_candidate_locator_field_count": len(REQUIRED_LOCATOR_FIELDS),
        "candidate_locator_missing_reason_counts": missing_counts,
        "language_counts": language_counts(records),
        "lane_refs": sorted({record["lane_ref"] for record in records if record.get("lane_ref")}),
        "required_status_family": EXPECTED_STATUS_FAMILY,
        "next_recommendation": (
            "build_private_source_locator_index_for_top_lanes_before_execution"
        ),
        "next_recommendation_requirements": [
            "populate_source_adapter_candidate_ref_hash",
            "populate_private_locator_ref_hash",
            "populate_source_root_label_hash",
            "populate_lane_candidate_family_hash",
            "populate_private_execution_context_ref_hash",
            "rerun_locator_preflight_before_private_execution",
        ],
        "non_actions": [
            "does_not_execute",
            "does_not_hydrate",
            "does_not_replay",
            "does_not_use_network",
            "does_not_train",
            "does_not_admit",
            "does_not_package",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "artifact_refs": {
            "locator_requirement_records": "stage12470_locator_requirement_records_jsonl",
            "guardrail_scan": "stage12470_guardrail_scan_json",
            "local_summary": "stage12470_local_summary_json",
            "summary": "stage12470_summary_json",
        },
        "stage_blockers": sorted(set(stage_blockers)),
        "upstream_context": {
            "stage12468_decision": stage12468_summary.get("decision"),
            "stage12468_return_file_present": stage12468_summary.get("return_file_present"),
            "stage12469_decision": stage12469_summary.get("decision"),
            "stage12469_request_count": stage12469_summary.get("request_count"),
        },
    }

    public_payload = {"summary": summary, "locator_requirement_records": records}
    scan_issues = public_scan("stage12470_public_artifacts", public_payload)
    preflight_passed = not scan_issues and actionable_count > 0 and not stage_blockers
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12470_guardrail_scan_v1",
        "scan_scope": "stage12470_public_summary_and_locator_requirement_records",
        "policy": "public_safe_hash_status_label_ref_counts_only_no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        "scan_status": "blocked_missing_private_locator_index" if blocked_count else "completed",
        "scan_passed": preflight_passed,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "blocker_codes": sorted(set(stage_blockers)),
    }
    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["stage_blockers"] = sorted(
            set([*summary["stage_blockers"], "stage12470_public_guardrail_scan_failed"])
        )
    summary["locator_preflight_passed"] = preflight_passed
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["artifact_hashes"] = {
        "locator_requirement_records": stable_hash(records),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash(
        {
            "decision": summary["decision"],
            "work_item_count": summary["work_item_count"],
            "blocked_locator_requirement_count": summary[
                "blocked_locator_requirement_count"
            ],
            "stage_blockers": summary["stage_blockers"],
            "raw_leak_count": summary["raw_leak_count"],
        }
    )

    write_jsonl(LOCATOR_REQUIREMENTS_OUT, records)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "work_item_count": summary["work_item_count"],
                "actionable_locator_requirement_count": actionable_count,
                "blocked_locator_requirement_count": blocked_count,
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
