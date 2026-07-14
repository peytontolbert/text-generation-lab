#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ARTIFACTS = ROOT / "runs" / "local" / "artifacts"
STAGE = 10971
NAME = "stage10971_immediate_evidence_replenishment_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "immediate_evidence_replenishment_audit.json"
BUNDLE_ROWS = ARTIFACTS / "stage10970_immediate_evidence_replenishment_bundle" / "bundle_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    rows = load_jsonl(BUNDLE_ROWS)
    missing_selected_test_anchor = []
    missing_gold_evidence_visibility = []
    identical_candidate_and_verifier_lines = []
    duplicate_option_values = []
    bundle_counts: dict[str, int] = defaultdict(int)

    for row in rows:
        row_id = str(row.get("row_id") or "")
        bundle_id = str(row.get("bundle_id") or "unknown")
        bundle_counts[bundle_id] += 1
        prompt = str(row.get("prompt_text") or row.get("input_text") or "")
        evidence_block = ""
        if "Evidence:\n" in prompt and "\nOptions:\n" in prompt:
            evidence_block = prompt.split("Evidence:\n", 1)[1].split("\nOptions:\n", 1)[0]
        evidence_lines = [line.strip() for line in evidence_block.splitlines() if line.strip()]
        gold_value = str(((row.get("standalone_projection_source") or {}).get("gold_value") or ""))
        selected_tests = list(row.get("selected_tests") or [])
        option_values = [str(item.get("value") or "") for item in (row.get("opaque_options") or []) if isinstance(item, dict)]

        if len(option_values) != len(set(option_values)):
            duplicate_option_values.append(row_id)
        if gold_value and not any(line.startswith(gold_value) for line in evidence_lines):
            missing_gold_evidence_visibility.append(row_id)
        if gold_value == "verifier_and_test_constraint" and selected_tests and not any(test in prompt for test in selected_tests):
            missing_selected_test_anchor.append(row_id)

        candidate_line = next((line for line in evidence_lines if line.startswith("candidate_change_surface")), "")
        verifier_line = next((line for line in evidence_lines if line.startswith("verifier_and_test_constraint")), "")
        if candidate_line and verifier_line and candidate_line == verifier_line:
            identical_candidate_and_verifier_lines.append(row_id)

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": not any([
            missing_selected_test_anchor,
            missing_gold_evidence_visibility,
            identical_candidate_and_verifier_lines,
            duplicate_option_values,
        ]),
        "source_bundle_rows": rel(BUNDLE_ROWS),
        "metrics": {
            "rows": len(rows),
            "bundle_counts": dict(sorted(bundle_counts.items())),
            "missing_selected_test_anchor_rows": len(missing_selected_test_anchor),
            "missing_gold_evidence_visibility_rows": len(missing_gold_evidence_visibility),
            "identical_candidate_and_verifier_rows": len(identical_candidate_and_verifier_lines),
            "duplicate_option_value_rows": len(duplicate_option_values),
        },
        "row_ids": {
            "missing_selected_test_anchor": missing_selected_test_anchor,
            "missing_gold_evidence_visibility": missing_gold_evidence_visibility,
            "identical_candidate_and_verifier_lines": identical_candidate_and_verifier_lines,
            "duplicate_option_values": duplicate_option_values,
        },
        "findings": [
            "This audit checks immediate replenishment rows for the specific eval-hacking risks that previously caused evidence aliasing or hidden-gold failures.",
            "A passing result means gold evidence is visible, verifier-ledger rows actually surface their selected tests, and candidate-surface/verifier lines are textually distinct.",
        ],
        "next_best_step": "If this passes, use stage10970 as the stable immediate replenishment package for the next support-package or review step; if it fails, repair the offending rows before any new probe.",
    }
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
