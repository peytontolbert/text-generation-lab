#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12323_v4_event_local_review_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12320_SCRIPT = ROOT / "scripts/build_stage12320_event_local_semantic_review_admission.py"
STAGE12321 = ROOT / "runs/local/artifacts/stage12321_remaining_v4_event_local_candidate_materializer/remaining_v4_event_local_parent_candidates.jsonl"
STAGE12317 = ROOT / "runs/local/artifacts/stage12317_event_local_observation_train_support_500/event_local_observation_train_support_tasks.jsonl"
STAGE12318 = ROOT / "runs/local/artifacts/stage12318_event_local_observation_package_qc/event_local_observation_qc_records.jsonl"
STAGE12320_ADMITTED = ROOT / "runs/local/artifacts/stage12320_event_local_semantic_review_admission/event_local_observation_train_support_admitted_rows.jsonl"

MAX_ADDITIONAL_V4_ADMISSIONS = 50
MAX_PER_CHAT = 3
MAX_PER_SOURCE_HASH = 3
MAX_PER_BUCKET = 12


def load_stage12320():
    spec = importlib.util.spec_from_file_location("stage12320_mod", STAGE12320_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load stage12320 module")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    mod = load_stage12320()
    parent_candidates = read_jsonl(STAGE12321)
    stage12317_by_id = {row.get("row_id"): row for row in read_jsonl(STAGE12317)}
    qc_by_source = {row.get("source_row_id"): row for row in read_jsonl(STAGE12318)}
    already_admitted_source_ids = {row.get("source_row_id") for row in read_jsonl(STAGE12320_ADMITTED)}

    linked_rows: list[dict[str, Any]] = []
    blocked_link_refs = []
    for parent in parent_candidates:
        for ref in parent.get("linked_event_local_qc_refs") or []:
            source_row_id = ref.get("stage12317_row_id")
            if not source_row_id or source_row_id in already_admitted_source_ids:
                blocked_link_refs.append(
                    {
                        "task_window_id": parent.get("task_window_id"),
                        "stage12317_row_id": source_row_id,
                        "blocked_reason": "missing_or_already_admitted_source_row",
                    }
                )
                continue
            row = stage12317_by_id.get(source_row_id)
            qc = qc_by_source.get(source_row_id) or {}
            if not row:
                blocked_link_refs.append(
                    {
                        "task_window_id": parent.get("task_window_id"),
                        "stage12317_row_id": source_row_id,
                        "blocked_reason": "stage12317_row_missing",
                    }
                )
                continue
            blockers = mod.admission_blockers(row, qc.get("review_status"))
            if blockers:
                blocked_link_refs.append(
                    {
                        "task_window_id": parent.get("task_window_id"),
                        "stage12317_row_id": source_row_id,
                        "blocked_reason": "admission_blockers",
                        "blockers": blockers,
                    }
                )
                continue
            linked_rows.append(row)

    linked_rows.sort(key=lambda row: (mod.bucket(row), (row.get("source_refs") or {}).get("chat_id_hash") or "", row.get("row_id") or ""))
    selected = []
    per_chat: Counter[str] = Counter()
    per_source_hash: Counter[str] = Counter()
    per_bucket: Counter[str] = Counter()
    seen_windows = set()
    for row in linked_rows:
        refs = row.get("source_refs") or {}
        chat = refs.get("chat_id_hash") or "unknown_chat"
        source_hash = refs.get("source_file_hash_compat") or "unknown_source_hash"
        task_window_id = refs.get("task_window_id")
        cand_bucket = mod.bucket(row)
        if task_window_id in seen_windows:
            continue
        if per_chat[chat] >= MAX_PER_CHAT:
            continue
        if per_source_hash[source_hash] >= MAX_PER_SOURCE_HASH:
            continue
        if per_bucket[cand_bucket] >= MAX_PER_BUCKET:
            continue
        selected.append(row)
        seen_windows.add(task_window_id)
        per_chat[chat] += 1
        per_source_hash[source_hash] += 1
        per_bucket[cand_bucket] += 1
        if len(selected) >= MAX_ADDITIONAL_V4_ADMISSIONS:
            break

    admitted = []
    for idx, row in enumerate(selected, 1):
        train_row = mod.make_train_row(row, idx)
        train_row["stage"] = STAGE
        train_row["row_id"] = f"stage12323::{row.get('row_id')}"
        train_row["source_stage"] = "stage12317_linked_from_stage12321_v4"
        train_row["dominance_controls"] = {
            "selection_rank": idx,
            "max_per_chat": MAX_PER_CHAT,
            "max_per_source_hash": MAX_PER_SOURCE_HASH,
            "max_per_bucket": MAX_PER_BUCKET,
        }
        admitted.append(train_row)

    write_jsonl(OUT / "v4_event_local_train_support_admitted_rows.jsonl", admitted)
    if blocked_link_refs:
        write_jsonl(OUT / "v4_event_local_blocked_link_refs.jsonl", blocked_link_refs)

    rule_counts = Counter((row.get("target_only") or {}).get("semantic_rule_id") or "MISSING" for row in admitted)
    verifier_counts = Counter((row.get("target_only") or {}).get("verifier_status_class") or "MISSING" for row in admitted)
    patch_counts = Counter((row.get("target_only") or {}).get("patch_apply_status") or "MISSING" for row in admitted)
    risky_fields: Counter[str] = Counter()
    for row in admitted:
        for action in (((row.get("model_input_view") or {}).get("candidate_action_set") or {}).get("actions") or []):
            for key in action:
                if key in mod.RISKY_ACTION_KEYS or key.endswith("_ref"):
                    risky_fields[key] += 1

    summary = {
        "stage": STAGE,
        "decision": "v4_event_local_review_admission_complete",
        "claim_boundary": "Additional train-support rows only for V4-linked event-local observation/status objectives. No Level-3 repair, patch-trace, next-action policy, strict eval, or source-heldout claim.",
        "training_allowed": bool(admitted),
        "parent_candidates": len(parent_candidates),
        "linked_rows_reviewed": len(linked_rows),
        "already_admitted_or_missing_links": sum(1 for row in blocked_link_refs if row.get("blocked_reason") == "missing_or_already_admitted_source_row"),
        "admitted_train_support_rows": len(admitted),
        "blocked_link_refs": len(blocked_link_refs),
        "needs_stage12316_extraction_parents": sum(1 for row in parent_candidates if not row.get("linked_event_local_qc_refs")),
        "semantic_rule_counts": dict(rule_counts),
        "verifier_status_counts": dict(verifier_counts),
        "patch_apply_status_counts": dict(patch_counts),
        "per_bucket_selected": dict(per_bucket),
        "per_chat_selected_top": dict(per_chat.most_common(20)),
        "risky_model_input_candidate_action_field_counts": dict(risky_fields),
        "next_stage": {
            "stage": "stage12324_combined_train_support_ledger",
            "purpose": "Combine Stage12320, Stage12322, and Stage12323 admitted train-support rows and remaining gap to 500.",
            "training_allowed": False,
        },
    }
    (OUT / "v4_event_local_review_admission_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "V4_EVENT_LOCAL_REVIEW_ADMISSION_STAGE12323.md").write_text(
        "# Stage12323 V4 Event-Local Review Admission\n\n"
        "This stage admits additional V4-linked event-local observation/status train-support rows from existing Stage12317/12318 QC links.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
