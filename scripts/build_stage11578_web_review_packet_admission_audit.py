#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11578
NAME = "stage11578_web_review_packet_admission_audit"
OUT = ART / NAME
SUMMARY = OUT / "web_review_packet_admission_audit.json"
ROW_AUDIT = OUT / "web_review_packet_row_admission_audit.jsonl"

PACKETS = ART / "stage11577_web_candidate_review_packet_materializer/web_candidate_review_packets.jsonl"
ROWS = ART / "stage11577_web_candidate_review_packet_materializer/web_candidate_review_row_shells.jsonl"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def option_values(row: dict[str, Any]) -> list[str]:
    opts = (row.get("standalone_projection_source") or {}).get("opaque_options") or row.get("opaque_options") or []
    return [str(opt.get("value") or "") for opt in opts if opt.get("value") is not None]


def audit_row(row: dict[str, Any]) -> dict[str, Any]:
    anti = row.get("anti_cheat") or {}
    blockers: list[str] = []
    if not anti.get("observed_verifier_transition_present"):
        blockers.append("missing_observed_verifier_transition")
    if anti.get("requires_prompt_target_leak_review_before_training"):
        blockers.append("prompt_target_leak_review_required")
    if not row.get("bounded_choice_target_label") and row.get("task_type") == "verifier_outcome":
        blockers.append("missing_verifier_outcome_gold")
    if row.get("gold_status") in {"requires_observed_verifier_transition"}:
        blockers.append("gold_requires_verifier_transition")
    if len(option_values(row)) < 4:
        blockers.append("too_few_options")
    prompt = str(row.get("input_text") or "")
    if "Visible source evidence:\n\nVisible verifier" in prompt:
        blockers.append("empty_source_evidence")
    if "Visible verifier/test evidence:\n\nChoices:" in prompt:
        blockers.append("empty_verifier_evidence")
    return {
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "lane": row.get("lane"),
        "split_component": row.get("split_component"),
        "task_type": row.get("task_type"),
        "gold_status": row.get("gold_status"),
        "admitted_train": not blockers,
        "admitted_strict": False,
        "blockers": sorted(set(blockers)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    packets = load_jsonl(PACKETS)
    rows = load_jsonl(ROWS)
    row_audits = [audit_row(row) for row in rows]
    admitted_train = [row for row in row_audits if row["admitted_train"]]
    metrics = {
        "packets": len(packets),
        "rows": len(rows),
        "admitted_train_rows": len(admitted_train),
        "admitted_strict_rows": 0,
        "unique_roots": len({row.get("root_id") for row in rows}),
        "train_candidate_roots": len({p.get("root_id") for p in packets if p.get("split_component") == "train_candidate"}),
        "heldout_candidate_roots": len({p.get("root_id") for p in packets if p.get("split_component") == "heldout_candidate"}),
        "blockers": dict(Counter(blocker for row in row_audits for blocker in row["blockers"])),
        "rows_by_gold_status": dict(Counter(str(row.get("gold_status")) for row in rows)),
        "rows_by_task_type": dict(Counter(str(row.get("task_type")) for row in rows)),
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "review_packet_not_admitted_verifier_and_leak_review_required",
        "metrics": metrics,
        "training_authorized": False,
        "strict_eval_authorized": False,
        "next_required_actions": [
            "Install or recover Web repo dependencies in an isolated environment.",
            "Run focused verifier commands for selected test paths and attach raw logs.",
            "Finalize verifier_outcome gold labels from observed transitions.",
            "Run prompt-target leak review after deciding whether paths remain visible evidence or become opaque evidence IDs.",
        ],
        "claim_boundary": [
            "This audit intentionally blocks training on Stage11577 shells.",
            "The packet is useful as review material, not as supervised data yet.",
            "No GPU execution or model scoring is performed.",
        ],
        "source_artifacts": {"packets": rel(PACKETS), "rows": rel(ROWS)},
        "outputs": {"summary": rel(SUMMARY), "row_audit": rel(ROW_AUDIT)},
    }
    write_jsonl(ROW_AUDIT, row_audits)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "metrics": metrics}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
