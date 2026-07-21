#!/usr/bin/env python3
"""Coordinate the missing Stage12527 private binding-review return handoff.

Stage12531 consumes only public-safe Stage12530 dashboard/summary metadata and
the Stage12528 public return schema. It helps operators fill the missing return
destination or, if a return file is already present, directs validation back to
Stage12528. It does not read or write private return rows, inspect candidate
contents, claim readiness, write Stage12521 manifests, Stage12516 candidates,
Stage12503 rows, or emit training/admission/Level-3/patch-trace material.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12531_private_binding_review_return_coordination_guardrail"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12527 = "stage12527_private_binding_review_queue"
STAGE12528 = "stage12528_private_binding_review_return_preflight"
STAGE12530 = "stage12530_private_binding_review_return_presence_audit"
TARGET_RETURN_FILENAME = "private_binding_review_returns.jsonl"
SLOT_COUNT = 343

FALSE_GUARDS = {
    "readiness_fabricated": False,
    "stage12521_readiness_manifests_written": False,
    "candidate_returns_written": False,
    "validated_returns_written": False,
    "stage12516_candidate_rows_written": False,
    "stage12503_return_file_written": False,
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
    "policy_label_materialized": False,
    "level3_atom_materialized": False,
    "patch_trace_materialized": False,
    "raw_source_output_included": False,
    "raw_private_values_revealed": False,
    "candidate_file_contents_read": False,
    "candidate_raw_paths_emitted": False,
    "return_file_contents_read": False,
    "readiness_claimed": False,
}
ZERO_GUARDS = {
    "stage12521_readiness_manifest_count": 0,
    "candidate_return_records_written": 0,
    "validated_return_records_written": 0,
    "stage12516_candidate_row_count": 0,
    "stage12503_return_records_written": 0,
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "level3_admitted": 0,
    "level3_atom_count": 0,
    "patch_trace_admitted": 0,
    "patch_trace_rows": 0,
    "policy_labels_emitted": 0,
    "proof_rows_emitted": 0,
    "executor_return_records_written": 0,
    "accepted_private_review_status_count": 0,
    "ready_review_status_count": 0,
    "ready_candidate_count": 0,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output|verifier output|commit:)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "raw",
    "raw_output",
    "raw_outputs",
    "raw_diff",
    "diff",
    "patch",
    "command",
    "commands",
    "cmd",
    "path",
    "paths",
    "file_path",
    "candidate_name",
    "candidate_ref_hash",
    "source",
    "source_text",
    "source_content",
    "verifier_output",
    "stdout",
    "stderr",
    "terminal_output",
    "policy_label",
    "policy_label_hash",
    "training_row",
    "training_rows",
    "admitted_row",
    "level3_atom",
    "patch_trace",
    "proof_row",
}


class RawLeakError(ValueError):
    pass


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
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


def scan_raw_leaks(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PUBLIC_KEYS:
                issues.append(stable_hash({"forbidden_key": key}))
            issues.extend(scan_raw_leaks(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan_raw_leaks(child))
    return issues


def enforce_no_raw_leaks(value: Any) -> None:
    issues = scan_raw_leaks(value)
    if issues:
        raise RawLeakError(f"stage12531 raw leak guard rejected {len(issues)} public field(s)")


def target_return_exists(root: Path) -> bool:
    return (root / "runs/local/artifacts" / STAGE12527 / TARGET_RETURN_FILENAME).exists()


def prior_stage12528(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12528
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12528}.json"),
        "schema": read_json(artifacts / "private_binding_review_return_schema.json"),
    }


def prior_stage12530(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12530
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12530}.json"),
        "dashboard": read_jsonl(artifacts / "private_binding_review_missing_return_dashboard.jsonl"),
    }


def return_contract(schema: dict[str, Any]) -> dict[str, Any]:
    contract = {
        "return_record_type": schema.get("return_record_type", "stage12528_private_binding_review_return_v1"),
        "required_public_safe_return_fields": list(schema.get("required_public_safe_return_fields") or []),
        "allowed_review_actions": list(schema.get("allowed_review_actions") or []),
        "ready_review_actions": list(schema.get("ready_review_actions") or []),
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
        "destination_token": f"{STAGE12527}::{TARGET_RETURN_FILENAME}",
    }
    enforce_no_raw_leaks(contract)
    return contract


def slot_context(stage12530: dict[str, Any], stage12528: dict[str, Any]) -> int:
    for summary in [stage12530["summary"], stage12528["summary"]]:
        value = summary.get("preserved_slot_count_context")
        if isinstance(value, int) and value > 0:
            return value
    return SLOT_COUNT


def checklist_rows(
    dashboard: list[dict[str, Any]],
    contract: dict[str, Any],
    return_present: bool,
    preserved_slot_count_context: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if dashboard:
        iterable = sorted(dashboard, key=lambda row: int(row.get("work_order_shard_index") or 0))
    else:
        iterable = [
            {
                "work_order_shard_index": 0,
                "work_order_shard_count": 0,
                "work_order_item_count": 0,
                "candidate_binding_source_id_hashes": [],
                "private_review_packet_id_hashes": [],
            }
        ]

    action_code = (
        "rerun_stage12528_private_binding_review_return_preflight"
        if return_present
        else "supply_stage12527_private_binding_review_returns_jsonl"
    )
    blocker_code = (
        "return_file_present_stage12528_validation_pending"
        if return_present
        else "stage12527_private_binding_review_returns_jsonl_absent"
    )

    for source_row in iterable:
        row = {
            "record_type": "stage12531_private_binding_review_return_coordination_checklist_v1",
            "coordination_row_id_hash": stable_hash(
                {
                    "shard": source_row.get("work_order_shard_index"),
                    "return_present": return_present,
                    "action": action_code,
                }
            ),
            "work_order_shard_id_hash": source_row.get("work_order_shard_id_hash"),
            "work_order_shard_index": int(source_row.get("work_order_shard_index") or 0),
            "work_order_shard_count": int(source_row.get("work_order_shard_count") or 0),
            "work_order_item_count": int(source_row.get("work_order_item_count") or 0),
            "candidate_binding_source_id_hashes": list(source_row.get("candidate_binding_source_id_hashes") or []),
            "private_review_packet_id_hashes": list(source_row.get("private_review_packet_id_hashes") or []),
            "target_return_stage": STAGE12527,
            "target_return_filename": TARGET_RETURN_FILENAME,
            "destination_token": contract["destination_token"],
            "return_file_present": return_present,
            "return_file_contents_read": False,
            "required_operator_action_code": action_code,
            "blocker_code": blocker_code,
            "required_validation_stage": STAGE12528,
            "stage12528_validation_required": return_present,
            "required_return_field_count": len(contract["required_public_safe_return_fields"]),
            "allowed_review_actions": contract["allowed_review_actions"],
            "ready_review_actions": contract["ready_review_actions"],
            "public_safe_metadata_only": True,
            "preserved_slot_count_context": preserved_slot_count_context,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def validation_gate(contract: dict[str, Any], return_present: bool, preserved_slot_count_context: int) -> dict[str, Any]:
    gate = {
        "record_type": "stage12531_private_binding_review_return_validation_gate_v1",
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
        "destination_token": contract["destination_token"],
        "return_record_type": contract["return_record_type"],
        "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
        "allowed_review_actions": contract["allowed_review_actions"],
        "ready_review_actions": contract["ready_review_actions"],
        "return_file_present": return_present,
        "return_file_contents_read": False,
        "private_return_rows_created_by_stage": False,
        "required_validation_stage": STAGE12528,
        "validation_gate_status": "stage12528_validation_pending" if return_present else "blocked_until_return_file_supplied",
        "public_safe_metadata_only": True,
        "preserved_slot_count_context": preserved_slot_count_context,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    enforce_no_raw_leaks(gate)
    return gate


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12528 = prior_stage12528(root)
    stage12530 = prior_stage12530(root)
    contract = return_contract(stage12528["schema"])
    return_present = target_return_exists(root)
    preserved_slot_count_context = slot_context(stage12530, stage12528)
    dashboard = stage12530["dashboard"]
    checklist = checklist_rows(dashboard, contract, return_present, preserved_slot_count_context)
    gate = validation_gate(contract, return_present, preserved_slot_count_context)
    work_order_item_count = sum(int(row.get("work_order_item_count") or 0) for row in checklist)
    work_order_shard_count = sum(1 for row in checklist if int(row.get("work_order_shard_index") or 0) > 0)

    if not stage12530["summary"]:
        decision = "blocked_missing_stage12530_presence_audit_summary"
    elif return_present:
        decision = "return_file_present_rerun_stage12528_validation_no_stage12531_parse"
    else:
        decision = "blocked_missing_private_binding_review_return_coordination_guardrail_emitted"

    summary = {
        "stage": STAGE,
        "record_type": "stage12531_private_binding_review_return_coordination_guardrail_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12531 coordinates the Stage12527 private binding-review return handoff using "
            "only public-safe Stage12530 and Stage12528 metadata. It never reads return-file "
            "contents and never fabricates readiness, returns, training rows, Level-3 rows, or "
            "patch traces."
        ),
        "source_stages": [STAGE12530, STAGE12528],
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
        "destination_token": contract["destination_token"],
        "return_file_present": return_present,
        "return_file_contents_read": False,
        "stage12530_decision": stage12530["summary"].get("decision"),
        "stage12530_return_file_present": stage12530["summary"].get("return_file_present"),
        "stage12530_dashboard_row_count": len(dashboard),
        "coordination_checklist_row_count": len(checklist),
        "work_order_item_count": work_order_item_count,
        "work_order_shard_count": work_order_shard_count,
        "stage12529_work_order_item_count": work_order_item_count,
        "stage12529_work_order_shard_count": work_order_shard_count,
        "stage12528_validation_required": return_present,
        "stage12528_validation_stage": STAGE12528,
        "next_stage": (
            "rerun_stage12528_private_binding_review_return_preflight_for_validation"
            if return_present
            else "private_reviewer_supplies_stage12527_private_binding_review_returns_jsonl"
        ),
        "return_record_type": contract["return_record_type"],
        "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
        "allowed_review_actions": contract["allowed_review_actions"],
        "ready_review_actions": contract["ready_review_actions"],
        "preserved_slot_count_context": preserved_slot_count_context,
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_binding_review_return_coordination_checklist.jsonl",
            "private_binding_review_return_validation_gate.json",
            "summary.json",
        ],
    }
    outputs = {"checklist": checklist, "gate": gate, "summary": summary, "guardrail": guardrail}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_binding_review_return_coordination_checklist.jsonl", checklist)
    write_json(out / "private_binding_review_return_validation_gate.json", gate)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
