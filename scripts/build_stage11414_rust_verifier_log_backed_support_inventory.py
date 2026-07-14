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
STAGE = 11414
NAME = "stage11414_rust_verifier_log_backed_support_inventory"
OUT = ART / NAME
SUMMARY = OUT / "rust_verifier_log_backed_support_inventory.json"
ROWS = OUT / "rust_verifier_log_backed_support_inventory_rows.jsonl"

INPUTS = [
    ART / "stage11410_rust_verifier_log_backed_partial_support/rust_verifier_log_backed_partial_support_rows.jsonl",
    ART / "stage11413_non_candle_rust_verifier_log_backed_support/non_candle_rust_verifier_log_backed_support_rows.jsonl",
]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    source_counts = {}
    for path in INPUTS:
        loaded = read_jsonl(path)
        source_counts[rel(path)] = len(loaded)
        rows.extend(loaded)
    roots = {str(row.get("root_id")) for row in rows}
    repos = {str(row.get("repo_family")) for row in rows}
    by_repo = Counter(str(row.get("repo_family")) for row in rows)
    by_target = Counter(str(row.get("semantic_target_value")) for row in rows)
    leak_ok = all(
        (row.get("anti_cheat") or {}).get("source_text_materialized")
        and (row.get("anti_cheat") or {}).get("target_label_not_visible_before_options")
        and (row.get("anti_cheat") or {}).get("actual_verifier_log_attached")
        and row.get("train_support_only")
        and not row.get("strict_eval_eligible")
        for row in rows
    )
    gate = {
        "anti_cheat_passed": leak_ok,
        "actual_verifier_logs_attached": bool(rows),
        "minimum_roots_met": len(roots) >= 10,
        "minimum_repo_breadth_met": len(repos) >= 3,
        "probe_ready": leak_ok and len(roots) >= 10 and len(repos) >= 3,
    }
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "rust_verifier_log_backed_support_inventory_not_probe_ready",
        "counts": {
            "train_support_rows": len(rows),
            "unique_roots": len(roots),
            "unique_repo_families": len(repos),
            "minimum_roots_required_before_probe": 10,
            "minimum_repo_families_required_before_probe": 3,
        },
        "source_counts": source_counts,
        "by_repo_family": dict(sorted(by_repo.items())),
        "by_target": dict(sorted(by_target.items())),
        "quality_gate": gate,
        "remaining_gap": {
            "additional_roots_needed": max(0, 10 - len(roots)),
            "additional_repo_families_needed": max(0, 3 - len(repos)),
        },
        "recommended_next_action": (
            "Acquire or materialize at least four more verifier-log-backed Rust roots from at least one new non-candle/non-git "
            "repo family, then rerun this inventory gate before any Rust support probe."
        ),
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
    }
    write_jsonl(ROWS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
