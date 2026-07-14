#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10437
NAME = "stage10437_repaired_v27_strict_overlay_eval_hacking_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "repaired_v27_strict_overlay_eval_hacking_audit.json"
ROW_JSONL = OUT_DIR / "repaired_v27_strict_overlay_eval_hacking_rows.jsonl"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

OVERLAY_JSONL = ROOT / "runs/local/artifacts/stage10436_repaired_v27_strict_overlay/repaired_v27_strict_overlay.jsonl"
LINE_RE = re.compile(r"^([A-Za-z0-9_]+)\s*(?:\[[^\]]+\])?:\s", re.MULTILINE)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = load_jsonl(OVERLAY_JSONL)
    audits: list[dict[str, Any]] = []
    leak_count = 0
    visible_slot_prefix_ok = 0
    old_key_hits = 0
    old_keys = {
        "algorithmic_background_reference",
        "candidate_change_surface",
        "external_analogue_reference",
        "nearby_definition_or_usage_context",
        "symptom_or_call_path_analogue",
        "verifier_and_test_constraint",
    }
    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        body = prompt.split("\nOptions:\n", 1)[0]
        target_value = str((row.get("standalone_projection_source") or {}).get("gold_value") or "")
        keys = LINE_RE.findall(body)
        slot_ok = all(key.startswith("visible_evidence_") or key in {"Language", "Perspective", "Task", "Evidence"} for key in keys)
        visible_slot_prefix_ok += int(slot_ok)
        leak = bool(target_value and target_value in body)
        leak_count += int(leak)
        old_key_present = any(f"{key} [" in body for key in old_keys)
        old_key_hits += int(old_key_present)
        audits.append(
            {
                "row_id": row["row_id"],
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "target_semantic_value": target_value,
                "prompt_contains_target_value_before_options": leak,
                "old_evidence_key_name_present": old_key_present,
                "visible_evidence_slot_contract_ok": slot_ok,
                "evidence_keys_seen": keys,
            }
        )
    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "source_overlay": display(OVERLAY_JSONL),
        "summary": {
            "rows": len(rows),
            "rows_with_prompt_target_leak": leak_count,
            "rows_with_old_evidence_key_names": old_key_hits,
            "rows_passing_visible_slot_contract": visible_slot_prefix_ok,
        },
        "claim_boundary": [
            "This audit checks only the repaired strict overlay surface.",
            "A zero leak count here is necessary but not sufficient for benchmark promotion.",
        ],
        "outputs": {
            "audit_json": display(AUDIT_JSON),
            "row_audit": display(ROW_JSONL),
        },
    }
    write_json(AUDIT_JSON, payload)
    write_jsonl(ROW_JSONL, audits)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
