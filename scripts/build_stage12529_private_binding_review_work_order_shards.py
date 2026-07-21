#!/usr/bin/env python3
"""Package Stage12527 private binding-review queue into reviewer work-order shards.

Stage12529 consumes only Stage12527 public-safe queue rows and Stage12528
public-safe return schema/blocker rows. It does not inspect candidate contents,
claim readiness, write Stage12521 manifests, executor returns, Stage12516
candidates, Stage12503 rows, or emit training/admission/Level-3/patch-trace
material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12529_private_binding_review_work_order_shards"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12527 = "stage12527_private_binding_review_queue"
STAGE12528 = "stage12528_private_binding_review_return_preflight"
TARGET_RETURN_FILENAME = "private_binding_review_returns.jsonl"
SHARD_SIZE = 20
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
        raise RawLeakError(f"stage12529 raw leak guard rejected {len(issues)} public field(s)")


def prior_stage12527(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12527
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12527}.json"),
        "queue": read_jsonl(artifacts / "private_review_queue.jsonl"),
    }


def prior_stage12528(root: Path) -> dict[str, Any]:
    artifacts = root / "runs/local/artifacts" / STAGE12528
    summaries = root / "runs/summaries"
    return {
        "summary": read_json(artifacts / "summary.json") or read_json(summaries / f"{STAGE12528}.json"),
        "schema": read_json(artifacts / "private_binding_review_return_schema.json"),
        "blockers": read_jsonl(artifacts / "private_binding_review_return_blockers.jsonl"),
    }


def queue_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("private_review_packet_id_hash") or ""),
        str(row.get("candidate_binding_source_id_hash") or ""),
    )


def preserved_slot_context(stage12527: dict[str, Any], stage12528: dict[str, Any]) -> int:
    for summary in [stage12527["summary"], stage12528["summary"]]:
        value = summary.get("preserved_slot_count_context")
        if isinstance(value, int) and value > 0:
            return value
    return SLOT_COUNT


def safe_return_contract(schema: dict[str, Any]) -> dict[str, Any]:
    contract = {
        "return_record_type": schema.get("return_record_type", "stage12528_private_binding_review_return_v1"),
        "required_public_safe_return_fields": list(schema.get("required_public_safe_return_fields") or []),
        "allowed_review_actions": list(schema.get("allowed_review_actions") or []),
        "ready_review_actions": list(schema.get("ready_review_actions") or []),
        "global_must_be_true_fields": list(schema.get("global_must_be_true_fields") or []),
        "global_must_be_false_fields": list(schema.get("global_must_be_false_fields") or []),
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
    }
    enforce_no_raw_leaks(contract)
    return contract


def eligible_pairs(queue: list[dict[str, Any]], blockers: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    queue_by_key = {queue_key(row): row for row in queue}
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()
    for blocker in blockers:
        key = queue_key(blocker)
        queue_row = queue_by_key.get(key)
        if queue_row is None or key in seen:
            continue
        pairs.append((queue_row, blocker))
        seen.add(key)
    pairs.sort(key=lambda item: int(item[0].get("priority_rank") or 0))
    return pairs


def work_order_items(pairs: list[tuple[dict[str, Any], dict[str, Any]]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, (queue_row, blocker) in enumerate(pairs, start=1):
        shard_index = (idx - 1) // SHARD_SIZE + 1
        row = {
            "record_type": "stage12529_private_binding_review_work_order_item_v1",
            "work_order_item_id_hash": stable_hash({"key": queue_key(queue_row), "idx": idx}),
            "work_order_shard_id_hash": stable_hash({"shard": shard_index}),
            "work_order_item_index": idx,
            "work_order_shard_index": shard_index,
            "private_review_packet_id_hash": queue_row.get("private_review_packet_id_hash"),
            "candidate_binding_source_id_hash": queue_row.get("candidate_binding_source_id_hash"),
            "candidate_class": queue_row.get("candidate_class"),
            "review_band": queue_row.get("review_band"),
            "priority_rank": queue_row.get("priority_rank"),
            "candidate_parent_name": queue_row.get("candidate_parent_name"),
            "candidate_suffix": queue_row.get("candidate_suffix"),
            "preserved_slot_count_context": queue_row.get("preserved_slot_count_context", SLOT_COUNT),
            "source_blocker_codes": blocker.get("blocker_codes", []),
            "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
            "allowed_review_actions": contract["allowed_review_actions"],
            "ready_review_actions": contract["ready_review_actions"],
            "target_return_stage": STAGE12527,
            "target_return_filename": TARGET_RETURN_FILENAME,
            "private_reviewer_must_write_return": True,
            "public_safe_metadata_only": True,
            "candidate_contents_read": False,
            "reviewer_work_order_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def shard_rows(items: list[dict[str, Any]], contract: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[int(item["work_order_shard_index"])].append(item)

    rows: list[dict[str, Any]] = []
    total_shards = len(grouped)
    for shard_index in sorted(grouped):
        shard_items = grouped[shard_index]
        class_counts = Counter(str(item.get("candidate_class")) for item in shard_items)
        band_counts = Counter(str(item.get("review_band")) for item in shard_items)
        row = {
            "record_type": "stage12529_private_binding_review_work_order_shard_v1",
            "work_order_shard_id_hash": stable_hash({"shard": shard_index}),
            "work_order_shard_index": shard_index,
            "work_order_shard_count": total_shards,
            "work_order_item_count": len(shard_items),
            "candidate_binding_source_id_hashes": [item["candidate_binding_source_id_hash"] for item in shard_items],
            "private_review_packet_id_hashes": [item["private_review_packet_id_hash"] for item in shard_items],
            "review_band_counts": dict(sorted(band_counts.items())),
            "candidate_class_counts": dict(sorted(class_counts.items())),
            "preserved_slot_count_context": SLOT_COUNT,
            "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
            "allowed_review_actions": contract["allowed_review_actions"],
            "target_return_stage": STAGE12527,
            "target_return_filename": TARGET_RETURN_FILENAME,
            "private_reviewer_must_write_return": True,
            "public_safe_metadata_only": True,
            "candidate_contents_read": False,
            "reviewer_work_order_only": True,
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        enforce_no_raw_leaks(row)
        rows.append(row)
    return rows


def blocked_checklist(stage12527: dict[str, Any], stage12528: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not stage12527["queue"]:
        rows.append(
            {
                "record_type": "stage12529_private_binding_review_work_order_blocker_v1",
                "blocker_id_hash": stable_hash("stage12527_queue_absent"),
                "blocker_code": "stage12527_private_review_queue_absent",
                "required_input": "stage12527_private_review_queue_public_safe_rows",
                "preserved_slot_count_context": preserved_slot_context(stage12527, stage12528),
                "public_safe_metadata_only": True,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    if not stage12528["blockers"]:
        rows.append(
            {
                "record_type": "stage12529_private_binding_review_work_order_blocker_v1",
                "blocker_id_hash": stable_hash("stage12528_blockers_absent"),
                "blocker_code": "stage12528_private_binding_review_return_blockers_absent",
                "required_input": "stage12528_missing_return_blocker_rows",
                "preserved_slot_count_context": preserved_slot_context(stage12527, stage12528),
                "public_safe_metadata_only": True,
                **FALSE_GUARDS,
                **ZERO_GUARDS,
            }
        )
    for row in rows:
        enforce_no_raw_leaks(row)
    return rows


def build(root: Path = ROOT) -> dict[str, Any]:
    out = root / "runs/local/artifacts" / STAGE
    stage12527 = prior_stage12527(root)
    stage12528 = prior_stage12528(root)

    contract = safe_return_contract(stage12528["schema"])
    pairs = eligible_pairs(stage12527["queue"], stage12528["blockers"])
    items = work_order_items(pairs, contract)
    shards = shard_rows(items, contract)
    blockers = blocked_checklist(stage12527, stage12528)
    class_counts = Counter(str(row.get("candidate_class")) for row in items)
    band_counts = Counter(str(row.get("review_band")) for row in items)

    if not stage12527["queue"] or not stage12528["blockers"]:
        decision = "blocked_missing_stage12527_queue_or_stage12528_blockers"
    elif items:
        decision = "private_reviewer_work_order_shards_emitted_no_readiness_claimed"
    else:
        decision = "blocked_no_stage12528_blockers_matched_stage12527_queue"

    summary = {
        "stage": STAGE,
        "record_type": "stage12529_private_binding_review_work_order_shards_summary_v1",
        "decision": decision,
        "claim_boundary": (
            "Stage12529 packages Stage12527 public-safe queue identities and Stage12528 "
            "return-schema/blocker rows into private-review work-order shards. It does not "
            "read candidate contents, claim readiness, write Stage12521 manifests, executor "
            "returns, Stage12516 candidates, Stage12503 rows, training/admission material, "
            "Level-3 atoms, or patch-trace material."
        ),
        "source_stages": [STAGE12527, STAGE12528],
        "stage12527_private_review_queue_count": len(stage12527["queue"]),
        "stage12528_return_blocker_count": len(stage12528["blockers"]),
        "work_order_item_count": len(items),
        "work_order_shard_count": len(shards),
        "shard_size": SHARD_SIZE,
        "preserved_slot_count_context": preserved_slot_context(stage12527, stage12528),
        "candidate_class_counts": dict(sorted(class_counts.items())),
        "review_band_counts": dict(sorted(band_counts.items())),
        "required_public_safe_return_fields": contract["required_public_safe_return_fields"],
        "allowed_review_actions": contract["allowed_review_actions"],
        "target_return_stage": STAGE12527,
        "target_return_filename": TARGET_RETURN_FILENAME,
        "blocked_work_order_input_count": len(blockers),
        "guardrail_scan_passed": True,
        "raw_leak_count": 0,
        "next_stage": "private_human_reviewer_supplies_stage12528_return_file_no_readiness_claimed",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }
    guardrail = {
        "stage": STAGE,
        "scan_passed": True,
        "raw_leak_count": 0,
        "raw_leak_issue_hashes": [],
        "scanned_outputs": [
            "private_binding_review_work_order_items.jsonl",
            "private_binding_review_work_order_shards.jsonl",
            "private_binding_review_work_order_blockers.jsonl",
            "summary.json",
        ],
    }
    outputs = {"items": items, "shards": shards, "blockers": blockers, "summary": summary, "guardrail": guardrail}
    enforce_no_raw_leaks(outputs)

    write_jsonl(out / "private_binding_review_work_order_items.jsonl", items)
    write_jsonl(out / "private_binding_review_work_order_shards.jsonl", shards)
    write_jsonl(out / "private_binding_review_work_order_blockers.jsonl", blockers)
    write_json(out / "guardrail_scan.json", guardrail)
    write_json(out / "summary.json", summary)
    write_json(root / "runs/summaries" / f"{STAGE}.json", summary)
    return summary


def main() -> None:
    build(ROOT)


if __name__ == "__main__":
    main()
