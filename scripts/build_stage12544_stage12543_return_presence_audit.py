#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12544_stage12543_return_presence_audit"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12543 = "stage12543_remaining_gap_execution_request"
STAGE12543_OUT = ROOT / "runs/local/artifacts" / STAGE12543
STAGE12543_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12543}.json"
STAGE12543_WORK_ITEMS = STAGE12543_OUT / "stage12543_remaining_gap_execution_work_items.jsonl"
STAGE12543_RUNBOOK = STAGE12543_OUT / "stage12543_executor_runbook.json"

RETURN_FILENAMES = [
    "stage12543_executor_returns.jsonl",
    "stage12543_remaining_gap_executor_returns.jsonl",
    "private_stage12543_executor_returns.jsonl",
]

RETURN_PRESENCE_NAME = "stage12544_stage12543_return_presence_rows.jsonl"
MISSING_RETURN_WORKLIST_NAME = "stage12544_missing_executor_return_worklist.jsonl"
AUDIT_NAME = "stage12544_return_presence_audit.json"


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists():
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
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                value["__line_no"] = line_no
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


def risky_claims_false() -> dict[str, Any]:
    return {
        "training_allowed": False,
        "countable_train_support": False,
        "strict_eval_eligible": False,
        "source_heldout_admissible": False,
        "level3_admitted": False,
        "level4_admitted": False,
        "patch_trace_admitted": False,
        "repair_claim_admitted": False,
        "fail_to_pass_claim_admitted": False,
    }


def return_paths() -> list[Path]:
    return [STAGE12543_OUT / name for name in RETURN_FILENAMES]


def load_return_index(paths: list[Path], expected_ids: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, int]]:
    index: dict[str, list[dict[str, Any]]] = {}
    stats = {"rows_seen": 0, "valid_matching_rows": 0, "malformed_rows": 0, "unknown_id_rows": 0, "duplicate_rows": 0}
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                stats["rows_seen"] += 1
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    stats["malformed_rows"] += 1
                    continue
                if not isinstance(value, dict) or not isinstance(value.get("work_item_id"), str):
                    stats["malformed_rows"] += 1
                    continue
                work_item_id = value["work_item_id"]
                if work_item_id not in expected_ids:
                    stats["unknown_id_rows"] += 1
                    continue
                if work_item_id in index:
                    stats["duplicate_rows"] += 1
                index.setdefault(work_item_id, []).append({
                    "return_file_hash": file_hash(path),
                    "return_row_number": line_no,
                })
                stats["valid_matching_rows"] += 1
    return index, stats


def build_presence_rows(work_items: list[dict[str, Any]], return_index: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows = []
    for item in work_items:
        work_item_id = item.get("work_item_id")
        matches = return_index.get(str(work_item_id), [])
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12544_stage12543_return_presence_row_v2",
                "work_item_id": work_item_id,
                "target_status_needed": item.get("target_status_needed"),
                "repo_family_hash": item.get("repo_family_hash"),
                "language_family": item.get("language_family"),
                "return_present": bool(matches),
                "matching_return_row_count": len(matches),
                "return_file_hashes": sorted({match["return_file_hash"] for match in matches}),
                "candidate_row_emitted": False,
                **risky_claims_false(),
            }
        )
    return rows

def build_missing_worklist(work_items: list[dict[str, Any]], runbook: dict[str, Any], present_ids: set[str] | None = None) -> list[dict[str, Any]]:
    public_fields = runbook.get("executor_output_contract", {}).get("required_public_return_fields", [])
    rows = []
    present_ids = present_ids or set()
    missing_items = [item for item in work_items if str(item.get("work_item_id")) not in present_ids]
    for index, item in enumerate(missing_items, 1):
        rows.append(
            {
                "stage": STAGE,
                "record_type": "stage12544_missing_executor_return_work_item_v1",
                "priority": index,
                "work_item_id": item.get("work_item_id"),
                "target_status_needed": item.get("target_status_needed"),
                "repo_family_hash": item.get("repo_family_hash"),
                "language_family": item.get("language_family"),
                "missing_return_reason": "stage12543_executor_return_file_absent",
                "accepted_return_filenames": RETURN_FILENAMES,
                "required_public_return_fields": public_fields,
                "raw_public_content_allowed": False,
                "selected_or_exact_test_scope_allowed": False,
                "controlled_fixture_like_allowed": False,
                "stage_synthetic_repo_family_allowed": False,
                "projection_or_transition_derived_label_allowed": False,
                "candidate_row_emitted": False,
                **risky_claims_false(),
            }
        )
    return rows


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12543_summary = read_json(STAGE12543_SUMMARY)
    work_items = read_jsonl(STAGE12543_WORK_ITEMS)
    runbook = read_json(STAGE12543_RUNBOOK)
    existing_returns = [path for path in return_paths() if path.exists()]
    expected_ids = {str(item.get("work_item_id")) for item in work_items if item.get("work_item_id")}
    return_index, return_stats = load_return_index(existing_returns, expected_ids)

    presence_rows = build_presence_rows(work_items, return_index)
    missing_worklist = build_missing_worklist(work_items, runbook, set(return_index))

    presence_path = OUT / RETURN_PRESENCE_NAME
    worklist_path = OUT / MISSING_RETURN_WORKLIST_NAME
    audit_path = OUT / AUDIT_NAME
    write_jsonl(presence_path, presence_rows)
    write_jsonl(worklist_path, missing_worklist)

    audit = {
        "stage": STAGE,
        "record_type": "stage12544_return_presence_audit_v1",
        "input_hashes": {
            "stage12543_summary": file_hash(STAGE12543_SUMMARY),
            "stage12543_work_items": file_hash(STAGE12543_WORK_ITEMS),
            "stage12543_runbook": file_hash(STAGE12543_RUNBOOK),
        },
        "stage12543_remaining_shortfall": stage12543_summary.get("stage12542_remaining_shortfall"),
        "stage12543_work_items": len(work_items),
        "accepted_return_filenames": RETURN_FILENAMES,
        "return_files_present": len(existing_returns),
        "return_rows_ingested": return_stats["valid_matching_rows"],
        "return_row_validation": return_stats,
        "candidate_rows_emitted": 0,
        "missing_return_work_items": len(missing_worklist),
        **risky_claims_false(),
    }
    write_json(audit_path, audit)

    summary = {
        "stage": STAGE,
        "record_type": "stage12544_stage12543_return_presence_summary_v1",
        "decision": "returns_complete_presence_only" if not missing_worklist else ("partial_returns_present_still_blocked" if return_index else "blocked_waiting_for_stage12543_executor_returns"),
        "claim_boundary": "Stage12544 checks for Stage12543 executor returns only. It performs no execution, emits no preflight rows, admits no countable support, and makes no training/Level3/repair/source-heldout claim.",
        "stage12543_remaining_shortfall": stage12543_summary.get("stage12542_remaining_shortfall"),
        "stage12543_work_items": len(work_items),
        "return_files_present": len(existing_returns),
        "return_rows_ingested": return_stats["valid_matching_rows"],
        "return_row_validation": return_stats,
        "new_preflight_row_count": 0,
        "new_countable_train_support_count": 0,
        "missing_return_work_items": len(missing_worklist),
        **risky_claims_false(),
        "artifact_refs": {
            "return_presence_rows": str(presence_path.relative_to(ROOT)),
            "missing_return_worklist": str(worklist_path.relative_to(ROOT)),
            "audit": str(audit_path.relative_to(ROOT)),
            "summary": str(SUMMARY.relative_to(ROOT)),
        },
    }
    write_json(SUMMARY, summary)
    return summary


if __name__ == "__main__":
    build()
