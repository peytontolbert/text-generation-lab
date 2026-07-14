#!/usr/bin/env python3
"""Roll Stage12007 targeted Python rows into transition support v11."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12008_transition_support_rollup_v11")
BASE = Path("runs/local/artifacts/stage12006_transition_support_rollup_v10/transition_support_rows_v10.jsonl")
ADDED = Path("runs/local/artifacts/stage12007_python_targeted_transition_rows/python_targeted_transition_rows.jsonl")
ROWS_OUT = ROOT / "transition_support_rows_v11.jsonl"
SUMMARY = ROOT / "transition_support_rollup_v11.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12008_transition_support_rollup_v11.json")
LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {
    "FAIL_TO_PASS": 50,
    "PASS_TO_PASS": 100,
    "PASS_CURRENT_BUILD": 40,
    "PASS_CURRENT_BUILD_AND_RUN": 40,
    "INSUFFICIENT_EVIDENCE": 40,
    "NOT_EXERCISED": 40,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict[str, Any]) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def remaining(counts: Counter[str], floors: dict[str, int]) -> dict[str, int]:
    return {key: max(0, floor - counts.get(key, 0)) for key, floor in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    duplicates = 0
    for source, path in [("stage12006", BASE), ("stage12007", ADDED)]:
        for row in read_jsonl(path):
            out = dict(row)
            out["stage12008_source"] = source
            out["split"] = "train"
            out["split_role"] = "stage12008_transition_support_v11_train_support_only"
            out["train_support_only"] = True
            out["strict_eval_eligible"] = False
            out["source_heldout_admissible"] = False
            key = (out.get("row_id"), root_key(out), out.get("observed_verifier_transition"))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(out)
    write_jsonl(ROWS_OUT, rows)
    lang = Counter(r.get("language_family") for r in rows)
    status = Counter(r.get("observed_verifier_transition") for r in rows)
    repo = Counter(r.get("repo_family") for r in rows)
    summary = {
        "stage": "stage12008_transition_support_rollup_v11",
        "base_rows_path": str(BASE),
        "added_rows_path": str(ADDED),
        "rows_path": str(ROWS_OUT),
        "base_rows": len(read_jsonl(BASE)),
        "added_rows": len(read_jsonl(ADDED)),
        "duplicate_rows_skipped": duplicates,
        "total_rows": len(rows),
        "unique_roots": len({root_key(r) for r in rows}),
        "language_counts": dict(sorted(lang.items())),
        "status_counts": dict(sorted(status.items())),
        "repo_family_counts_top25": dict(repo.most_common(25)),
        "remaining_language_floor": remaining(lang, LANGUAGE_FLOORS),
        "remaining_status_floor": remaining(status, STATUS_FLOORS),
        "decision": "support_inventory_v11_not_train_ready",
        "reason": "Python targeted rows improve PASS_TO_PASS and INSUFFICIENT_EVIDENCE supply, but floors remain far short and PASS_TO_PASS/NOT_EXERCISED gaps dominate.",
        "claim_boundary": "Support inventory only. No model promotion or Gemma comparison should be claimed from v11.",
        "next_stage_recommendation": {
            "stage": "stage12009_transition_root_250_rust_and_pass_to_pass_expansion",
            "action": "Prioritize independent Rust/Python PASS_TO_PASS roots and NOT_EXERCISED negatives; avoid another training run until floors are materially closer.",
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
