#!/usr/bin/env python3
"""Roll Stage11997 INSUFFICIENT_EVIDENCE rows into transition support v6."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path("runs/local/artifacts/stage11998_transition_support_rollup_v6")
BASE = Path("runs/local/artifacts/stage11996_transition_support_rollup_v5/transition_support_rows_v5.jsonl")
ADDED = Path("runs/local/artifacts/stage11997_insufficient_evidence_admission/insufficient_evidence_admitted_rows.jsonl")
ROWS_OUT = ROOT / "transition_support_rows_v6.jsonl"
SUMMARY = ROOT / "transition_support_rollup_v6.json"
SUMMARY_MIRROR = Path("runs/summaries/stage11998_transition_support_rollup_v6.json")
LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def row_key(row: dict) -> tuple[str | None, str | None, str | None]:
    return (row.get("row_id"), root_key(row), row.get("observed_verifier_transition"))


def rem(counts: Counter, floors: dict[str, int]) -> dict[str, int]:
    return {k: max(0, v - counts.get(k, 0)) for k, v in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows, seen, duplicates = [], set(), 0
    for src_name, path in [("stage11996", BASE), ("stage11997", ADDED)]:
        for row in read_jsonl(path):
            out = dict(row)
            out["stage11998_source"] = src_name
            out["split"] = "train"
            out["split_role"] = "stage11998_transition_support_v6_train_support_only"
            out["train_support_only"] = True
            out["strict_eval_eligible"] = False
            out["source_heldout_admissible"] = False
            key = row_key(out)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(out)
    write_jsonl(ROWS_OUT, rows)
    lang = Counter(r.get("language_family") for r in rows)
    status = Counter(r.get("observed_verifier_transition") for r in rows)
    repo = Counter(r.get("repo_family") for r in rows)
    roots = {root_key(r) for r in rows}
    executable_success = sum(1 for r in rows if r.get("observed_verifier_transition") in {"PASS_TO_PASS", "PASS_CURRENT_BUILD", "PASS_CURRENT_BUILD_AND_RUN", "FAIL_TO_PASS", "NOT_EXERCISED"})
    underhydrated = status.get("INSUFFICIENT_EVIDENCE", 0)
    summary = {
        "stage": "stage11998_transition_support_rollup_v6",
        "base_rows_path": str(BASE),
        "added_rows_path": str(ADDED),
        "rows_path": str(ROWS_OUT),
        "base_rows": len(read_jsonl(BASE)),
        "added_rows": len(read_jsonl(ADDED)),
        "duplicate_rows_skipped": duplicates,
        "total_rows": len(rows),
        "unique_roots": len(roots),
        "language_counts": dict(sorted(lang.items())),
        "status_counts": dict(sorted(status.items())),
        "repo_family_counts_top20": dict(repo.most_common(20)),
        "executable_or_observed_status_rows_excluding_insufficient": executable_success,
        "underhydrated_insufficient_evidence_rows": underhydrated,
        "remaining_language_floor": rem(lang, LANGUAGE_FLOORS),
        "remaining_status_floor": rem(status, STATUS_FLOORS),
        "decision": "support_inventory_v6_not_train_ready",
        "reason": "Negative status coverage improved, but FAIL_TO_PASS/PASS_TO_PASS/build-run and independent language-root floors remain too low for another serious transition training run.",
        "next_stage_recommendation": {
            "stage": "stage11999_fresh_executable_root_probe_plan",
            "action": "Mine fresh executable roots, prioritizing C/C++ and web plus controlled FAIL_TO_PASS from existing PASS_TO_PASS/build-run roots.",
        },
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__": main()
