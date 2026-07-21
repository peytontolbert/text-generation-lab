#!/usr/bin/env python3
"""Roll Stage12047 NOT_EXERCISED floor-closure rows into support v31."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path("runs/local/artifacts/stage12048_transition_support_rollup_v31")
BASE = Path("runs/local/artifacts/stage12046_transition_support_rollup_v30/transition_support_rows_v30.jsonl")
ADDED = Path("runs/local/artifacts/stage12047_not_exercised_floor_closure_rows/not_exercised_floor_closure_rows.jsonl")
ROWS_OUT = ROOT / "transition_support_rows_v31.jsonl"
SUMMARY = ROOT / "transition_support_rollup_v31.json"
SUMMARY_MIRROR = Path("runs/summaries/stage12048_transition_support_rollup_v31.json")
LANGUAGE_FLOORS = {"python": 50, "rust": 50, "c_cpp": 50, "web_js_ts_html": 50}
STATUS_FLOORS = {"FAIL_TO_PASS": 50, "PASS_TO_PASS": 100, "PASS_CURRENT_BUILD": 40, "PASS_CURRENT_BUILD_AND_RUN": 40, "INSUFFICIENT_EVIDENCE": 40, "NOT_EXERCISED": 40}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


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
    for source, path in [("stage12046", BASE), ("stage12047", ADDED)]:
        for row in read_jsonl(path):
            out = dict(row)
            out["stage12048_source"] = source
            out["split"] = "train"
            out["split_role"] = "stage12048_transition_support_v31_train_support_only"
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
    remaining_language = remaining(lang, LANGUAGE_FLOORS)
    remaining_status = remaining(status, STATUS_FLOORS)
    train_ready = all(v == 0 for v in remaining_language.values()) and all(v == 0 for v in remaining_status.values())
    summary = {
        "stage": "stage12048_transition_support_rollup_v31",
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
        "repo_family_counts_top30": dict(repo.most_common(30)),
        "remaining_language_floor": remaining_language,
        "remaining_status_floor": remaining_status,
        "train_ready_against_transition_root_250_floors": train_ready,
        "not_exercised_floor_closure_added": len(read_jsonl(ADDED)),
        "decision": "support_inventory_v31_not_train_ready" if not train_ready else "support_inventory_v31_floor_ready_requires_anti_cheat_audit",
        "reason": "NOT_EXERCISED floor is closed, but PASS_TO_PASS, FAIL_TO_PASS, and INSUFFICIENT_EVIDENCE floors remain unmet." if not train_ready else "Floor counts are met; run anti-cheat and split audits before training.",
        "claim_boundary": "Support inventory only. No model promotion or Gemma comparison should be claimed from v31.",
        "next_stage_recommendation": {"stage": "stage12049_status_floor_closure", "action": "Close PASS_TO_PASS, semantic FAIL_TO_PASS, and INSUFFICIENT_EVIDENCE floors; reduce high repo-family concentration where possible."},
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    SUMMARY_MIRROR.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
