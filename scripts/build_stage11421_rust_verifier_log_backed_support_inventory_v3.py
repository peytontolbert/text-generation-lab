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
STAGE = 11421
NAME = "stage11421_rust_verifier_log_backed_support_inventory_v3"
OUT = ART / NAME
SUMMARY = OUT / "rust_verifier_log_backed_support_inventory_v3.json"
ROWS = OUT / "rust_verifier_log_backed_support_inventory_v3_rows.jsonl"

INPUTS = [
    ART / "stage11410_rust_verifier_log_backed_partial_support/rust_verifier_log_backed_partial_support_rows.jsonl",
    ART / "stage11413_non_candle_rust_verifier_log_backed_support/non_candle_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11417_third_family_rust_verifier_log_backed_support/third_family_rust_verifier_log_backed_support_rows.jsonl",
    ART / "stage11420_perftree_rust_build_verifier_backed_support/perftree_rust_build_verifier_backed_support_rows.jsonl",
]
MIN_ROOTS = 10
MIN_REPO_FAMILIES = 3


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
    source_counts: dict[str, int] = {}
    for path in INPUTS:
        loaded = read_jsonl(path)
        source_counts[rel(path)] = len(loaded)
        rows.extend(loaded)

    roots = {str(row.get("root_id")) for row in rows}
    repos = {str(row.get("repo_family")) for row in rows}
    by_repo = Counter(str(row.get("repo_family")) for row in rows)
    by_target = Counter(str(row.get("semantic_target_value")) for row in rows)
    by_anchor_type = Counter("build_verifier_only" if row.get("build_verifier_only") else "selected_or_inline_test_anchor" for row in rows)
    build_verifier_roots = {str(row.get("root_id")) for row in rows if row.get("build_verifier_only")}
    selected_or_inline_roots = roots - build_verifier_roots
    leak_ok = bool(rows) and all(
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
        "minimum_roots_met": len(roots) >= MIN_ROOTS,
        "minimum_repo_breadth_met": len(repos) >= MIN_REPO_FAMILIES,
        "probe_ready": leak_ok and len(roots) >= MIN_ROOTS and len(repos) >= MIN_REPO_FAMILIES,
        "selected_or_inline_test_root_count": len(selected_or_inline_roots),
        "build_verifier_only_root_count": len(build_verifier_roots),
    }
    decision = "rust_verifier_log_backed_support_inventory_probe_ready"
    if not gate["probe_ready"]:
        decision = "rust_verifier_log_backed_support_inventory_not_probe_ready"

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": decision,
        "counts": {
            "train_support_rows": len(rows),
            "unique_roots": len(roots),
            "unique_repo_families": len(repos),
            "minimum_roots_required_before_probe": MIN_ROOTS,
            "minimum_repo_families_required_before_probe": MIN_REPO_FAMILIES,
        },
        "source_counts": source_counts,
        "by_repo_family": dict(sorted(by_repo.items())),
        "by_target": dict(sorted(by_target.items())),
        "by_anchor_type": dict(sorted(by_anchor_type.items())),
        "quality_gate": gate,
        "remaining_gap": {
            "additional_roots_needed": max(0, MIN_ROOTS - len(roots)),
            "additional_repo_families_needed": max(0, MIN_REPO_FAMILIES - len(repos)),
            "selected_test_rust_replenishment_still_needed": True,
        },
        "limitations": [
            "The root-count and repo-family support gate is met only after adding three Perftree build-verifier-only roots.",
            "Perftree rows have exact Cargo verifier commands and logs but no selected-test source anchors.",
            "This inventory can support a diagnostic Rust support package, but selected-test Rust verifier-transition replenishment remains incomplete.",
        ],
        "recommended_next_action": (
            "If a diagnostic Rust support probe is needed, use this inventory with build_verifier_only stratification and keep selected-test claims separate. "
            "For promotable Rust verifier-transition claims, acquire more selected-test anchored Rust roots."
        ),
        "outputs": {"summary": rel(SUMMARY), "rows": rel(ROWS)},
    }
    write_jsonl(ROWS, rows)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps(summary["counts"], indent=2, sort_keys=True))
    print(json.dumps(summary["quality_gate"], indent=2, sort_keys=True))
    print(json.dumps(summary["remaining_gap"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
