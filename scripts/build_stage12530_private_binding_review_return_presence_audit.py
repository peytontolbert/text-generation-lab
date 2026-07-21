#!/usr/bin/env python3
"""Audit Stage12529 private-review shard return presence.

Stage12530 consumes Stage12529 shard/item metadata plus the Stage12528 public
return schema/summary. It checks only whether the exact Stage12529 target return
file has been supplied under Stage12527. If absent, it emits a shard-level
missing-return dashboard and zero ready/accepted counts. If present, it does not
parse return rows; Stage12528 remains the validator for the public return schema.

It does not read raw candidate contents, write Stage12521 readiness manifests,
write executor returns, write Stage12516 candidates, write Stage12503 rows, or
emit training/admission/Level-3/patch-trace material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12530_private_binding_review_return_presence_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12527 = "stage12527_private_binding_review_queue"
STAGE12528 = "stage12528_private_binding_review_return_preflight"
STAGE12529 = "stage12529_private_binding_review_work_order_shards"
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
        raise RawLeakError(f"stage12530 raw leak guard rejected {len(issues)} public field(s)")


def stage12527_dir(root: Path) -> Path:
    return root / "runs/local/artifacts" / STAGE12527


def target_return_path(root: Path) -> Path:
    return stage12527_dir(root) / TARGET_RETURN_FILENAME


def prior_stage12528(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12528
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12528}.json"),
        "schema": read_json(artifacts / "private_binding_review_return_schema.json"),
    }


def prior_stage12529(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12529
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12529}.json"),
        "items": read_jsonl(artifacts / "private_binding_review_work_order_items.jsonl"),
        "shards": read_jsonl(artifacts / "private_binding_review_work_order_shards.jsonl"),
    }


def preserved_slot_context(stage12528: dict[str, Any], stage12529: dict[str, Any]) -> int:
    for summary in [stage12529["summary"], stage12528["summary"]]:
        value = summary.get("preserved_slot_count_context")
        if isinstance(value, int) and value > 0:
            return value
    return SLOT_COUNT


def schema_contract(schema: dict[str, Any]) -> dict[str, Any]:
    contract = {
        "return_schema_ref": "private_binding_review_return_schema.json",
        "return_record_type": schema.get("return_record_type", "stage12528_private_binding_review_return_v1"),
        "required_public_safe_return_fields": list(schema.get("required_public_safe_return_fields") or []),
        "allowed_review_actions": list(schema.get("allowed_review_actions") or []),
        "ready_review_actions": list(schema.get("ready_review_actions") or []),
    }
    enforce_no_raw_leaks(contract)
    return contract


def missing_return_dashboard(
    shards: list[dict[str, Any]],
    items: list[dict[str, Any]],
    return_present: bool,
    slot_context: int,
) -> list[dict[str, Any]]:
    item_counts = Counter(int(item.get("work_order_shard_index") or 0) for item in items)
    rows: list[dict[str, Any]] = []
    for shard in sorted(shards, key=lambda row: int(row.get("work_order_shard_index") or 0)):
        shard_index = int(shard.get("work_order_shard_index") or 0)
        row = {
            "record_type": "stage12530_private_binding_review_missing_return_dashboard_v1",
            "dashboard_row_id_hash": stable_hash({"shard": shard_index, "return_present": return_present}),
            "work_order_shard_id_hash": shard.get("work_order_shard_id_hash"),
            "work_order_shard_index": shard_index,
            "work_order_shard_count": shard.get("work_order_shard_count", len(shards)),
            "work_order_item_count": int(shard.get("work_order_item_count") or item_counts[shard_index]),
            "candidate_binding_source_id_hashes": list(shard.get("candidate_binding_source_id_hashes") or []),
            "private_review_packet_id_hashes": list(shard.get("private_review_packet_id_hashes") or []),
            "target_return_stage": STAGE12527,
            "target_return_filename": TARGET_RETURN_FILENAME,
            "return_file_present": return_present,
            "blocker_code": (
                "private_binding_review_return_file_present_stage12528_validation_required"
                if return_present
                else "stage12527_private_binding_review_returns_jsonl_absent"
            ),
            "required_next_stage": "stage12528_private_binding_review_return_preflight",
            "stage12528_validation_required": return_present,
            "public_safe_metadata_only": True,
            "preserved_slot_count_context": slot_context,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12528 = prior_stage12528(root)
    stage12529 = prior_stage12529(root)
    contract = schema_contract(stage12528["schema"])
    return_present = target_return_path(root).exists()
    slot_context = preserved_slot_context(stage12528, stage12529)

    items = stage12529["items"]
    shards = stage12529["shards"]
    dashboard = missing_return_dashboard(shards, items, return_present, slot_context)
    class_counts = Counter(str(row.get("candidate_class")) for row in items)
    band_counts = Counter(str(row.get("review_band")) for row in items)

    if not shards or not items:
        decision = "blocked_missing_stage12529_work_order_shards_or_items"
    elif return_present:
        decision = "return_file_present_stage12528_validation_required_no_stage12530_parse"
    else:
        decision = "blocked_missing_stage12527_private_binding_review_returns_dashboard_emitted"

    summary = {
        "stage": STAGE,
        "record_type": "stage12530_private_binding_review_return_presence_audit_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12530 audits only whether the exact Stage12529 target return file exists. "
            "It consumes Stage12529 public-safe shard/item metadata and Stage12528 public "
            "schema/summary, emits a missing-return dashboard when absent, and delegates all "
            "return-row validation to Stage12528 without parsing return file contents."
        ),
        "source_stages": [STAGE12529, STAGE12528],
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
        "return_file_present": return_present,
        "return_file_contents_read": False,
        "stage12528_validation_required": return_present,
        "stage12528_validation_stage": STAGE12528,
        "stage12528_validation_summary_decision": stage12528["summary"].get("decision"),
        "stage12528_prior_return_file_present": stage12528["summary"].get("return_file_present"),
        "stage12529_work_order_item_count": len(items),
        "stage12529_work_order_shard_count": len(shards),
        "stage12527_private_review_queue_count": stage12529["summary"].get("stage12527_private_review_queue_count", len(items)),
        "missing_return_dashboard_row_count": 0 if return_present else len(dashboard),
        "coordination_dashboard_row_count": len(dashboard),
        "preserved_slot_count_context": slot_context,
        "candidate_class_counts": dict(sorted(class_counts.items())),
        "review_band_counts": dict(sorted(band_counts.items())),
        "return_schema_ref": contract["return_schema_ref"],
        "return_record_type": contract["return_record_type"],
        "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
        "allowed_review_actions": contract["allowed_review_actions"],
        "ready_review_actions": contract["ready_review_actions"],
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": (
            "rerun_stage12528_private_binding_review_return_preflight_for_validation"
            if return_present
            else "private_reviewer_supplies_stage12527_private_binding_review_returns_jsonl"
        ),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_binding_review_missing_return_dashboard.jsonl",
            "summary.json",
        ],
    }
    outputs = {"dashboard": dashboard, "summary": summary, "guardrail": guardrail}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_binding_review_missing_return_dashboard.jsonl", dashboard)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
