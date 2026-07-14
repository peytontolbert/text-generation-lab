#!/usr/bin/env python3
"""Roll Stage12001 C++ benchmark transition rows into support v8."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12002_transition_support_rollup_v8")
BASE = Path("runs/local/artifacts/stage12000_fail_to_pass_admission_and_rollup/transition_support_rows_v7.jsonl")
ADDED = Path("runs/local/artifacts/stage12001_cpp_benchmark_transition_rows/cpp_benchmark_transition_rows.jsonl")
ROWS_OUT = ROOT / "transition_support_rows_v8.jsonl"
SUMMARY = ROOT / "transition_support_rollup_v8.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12002_transition_support_rollup_v8.json")
LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists(): return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def root_key(row: dict[str, Any]) -> str | None:
    return row.get("root_lineage_key") or row.get("root_id") or row.get("source_root_id") or row.get("source_bundle_id") or row.get("row_id")


def rem(counts: Counter, floors: dict[str, int]) -> dict[str, int]:
    return {k: max(0, v - counts.get(k, 0)) for k, v in floors.items()}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_MIRROR.parent.mkdir(parents=True, exist_ok=True)
    rows=[]; seen=set(); duplicates=0
    for src, path in [("stage12000", BASE), ("stage12001", ADDED)]:
        for row in read_jsonl(path):
            out=dict(row)
            out["stage12002_source"] = src
            out["split"] = "train"
            out["split_role"] = "stage12002_transition_support_v8_train_support_only"
            out["train_support_only"] = True
            out["strict_eval_eligible"] = False
            out["source_heldout_admissible"] = False
            key=(out.get("row_id"), root_key(out), out.get("observed_verifier_transition"))
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append(out)
    write_jsonl(ROWS_OUT, rows)
    lang=Counter(r.get("language_family") for r in rows)
    status=Counter(r.get("observed_verifier_transition") for r in rows)
    repo=Counter(r.get("repo_family") for r in rows)
    roots={root_key(r) for r in rows}
    summary={
        "stage":"stage12002_transition_support_rollup_v8",
        "base_rows_path":str(BASE),
        "added_rows_path":str(ADDED),
        "rows_path":str(ROWS_OUT),
        "base_rows":len(read_jsonl(BASE)),
        "added_rows":len(read_jsonl(ADDED)),
        "duplicate_rows_skipped":duplicates,
        "total_rows":len(rows),
        "unique_roots":len(roots),
        "language_counts":dict(sorted(lang.items())),
        "status_counts":dict(sorted(status.items())),
        "repo_family_counts_top20":dict(repo.most_common(20)),
        "remaining_language_floor":rem(lang, LANGUAGE_FLOORS),
        "remaining_status_floor":rem(status, STATUS_FLOORS),
        "decision":"support_inventory_v8_not_train_ready",
        "reason":"C/C++ build-run coverage improved, but PASS_TO_PASS/FAIL_TO_PASS/negative-status and language floors remain too low for serious training.",
        "claim_boundary":"Support inventory only. No 100M/Gemma frontier or full-product harness claim should be made from this rollup.",
        "next_stage_recommendation":{"stage":"stage12003_cpp_real_source_fail_to_pass_mutations","action":"Use benchmark passing C++ roots for restore-guarded real-source FAIL_TO_PASS mutations, then continue mining independent roots."},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True)+"\n")
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == "__main__": main()
