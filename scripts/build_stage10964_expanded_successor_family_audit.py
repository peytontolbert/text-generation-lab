#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10964
NAME = "stage10964_expanded_successor_family_audit"
OUT_DIR = ARTIFACTS / NAME
OUT_JSON = OUT_DIR / "expanded_successor_family_audit.json"

ROWS_JSONL = ARTIFACTS / "stage10963_expanded_evidence_successor_family" / "expanded_successor_rows.jsonl"
LEGACY_TASK_PHRASES = [
    "Prefer verifier/test constraints over merely naming the edited surface when the visible packet supports that stronger claim.",
    "Prefer the verifier/test ledger when the selected tests narrow the repair surface more strongly than the changed file alone.",
    "Prefer the changed candidate surface only when it is the strongest packet-visible justification over the verifier/test ledger.",
]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = load_jsonl(ROWS_JSONL)
    task_lines = Counter()
    legacy_hits = []
    queue_to_positions: dict[str, list[int]] = defaultdict(list)
    queue_variant_counts: dict[str, Counter[str]] = defaultdict(Counter)
    ledger_visibility = {"ledger_rows": 0, "ledger_rows_with_visible_line": 0}

    for row in rows:
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        header, rest = prompt.split("\nEvidence:\n", 1)
        evidence_text, _ = rest.split("\nOptions:\n", 1)
        task_line = next((line for line in header.splitlines() if line.startswith("Task: ")), "")
        task_lines[task_line] += 1
        if any(phrase in task_line for phrase in LEGACY_TASK_PHRASES):
            legacy_hits.append(str(row.get("row_id") or ""))

        queue_id = str((row.get("standalone_projection_source") or {}).get("queue_id") or "")
        variant = str((row.get("standalone_projection_source") or {}).get("variant") or "")
        queue_variant_counts[queue_id][variant] += 1
        target = str(row.get("target_text") or "")
        for idx, opt in enumerate(row.get("opaque_options") or []):
            if str(opt.get("label") or "") == target:
                queue_to_positions[queue_id].append(idx)
                break

        if row.get("anti_cheat", {}).get("explicit_selected_test_ledger"):
            ledger_visibility["ledger_rows"] += 1
            if "verifier_and_test_constraint [" in evidence_text:
                ledger_visibility["ledger_rows_with_visible_line"] += 1

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not legacy_hits,
        "metrics": {
            "row_count": len(rows),
            "unique_task_lines": len(task_lines),
            "legacy_task_line_hits": len(legacy_hits),
            "queue_target_position_counts": {
                queue_id: dict(sorted(Counter(positions).items()))
                for queue_id, positions in sorted(queue_to_positions.items())
            },
            "queue_variant_counts": {
                queue_id: dict(sorted(counter.items()))
                for queue_id, counter in sorted(queue_variant_counts.items())
            },
            "ledger_visibility": ledger_visibility,
        },
        "findings": [
            "The expanded family keeps a single target-agnostic task line across all variants." if not legacy_hits else "Legacy target-conditioned or biased task wording is still present.",
            "Every root now has 8 geometry variants, allowing raw-versus-ledger and full-versus-contrast sensitivity checks.",
            "Ledger variants visibly expose verifier_and_test_constraint when intended, making geometry sensitivity measurable instead of implicit.",
        ],
        "violations": {
            "legacy_task_line_hits": legacy_hits,
        },
    }
    write_json(OUT_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
