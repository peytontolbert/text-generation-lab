#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11195
NAME = "stage11195_clean_residual_successor_bank"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "clean_residual_successor_bank.json"
BANK_JSONL = OUT_DIR / "clean_residual_successor_bank.jsonl"
REPLACEMENT_MAP_JSONL = OUT_DIR / "replacement_map.jsonl"

CLEAN_OLD = ARTIFACTS / "stage11188_reserved_residual_validity_reconciliation/clean_reserved_residual_rows.jsonl"
QUARANTINED_OLD = ARTIFACTS / "stage11188_reserved_residual_validity_reconciliation/quarantined_reserved_residual_rows.jsonl"
PARTIAL_REPLACEMENTS = ARTIFACTS / "stage11191_partial_replacement_admission_audit/admitted_partial_replacement_rows.jsonl"
RUST_REPLACEMENTS = ARTIFACTS / "stage11194_rust_replacement_admission_audit/admitted_rust_replacement_rows.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "missing")


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("language_family") or "missing"), str(row.get("task_type") or "missing"))


def main() -> None:
    clean_old = load_jsonl(CLEAN_OLD)
    quarantined_old = load_jsonl(QUARANTINED_OLD)
    replacements = load_jsonl(PARTIAL_REPLACEMENTS) + load_jsonl(RUST_REPLACEMENTS)
    replacement_by_old = {str(row.get("replacement_for_blocked_row_id")): row for row in replacements}
    missing = [row for row in quarantined_old if str(row.get("row_id")) not in replacement_by_old]
    duplicate_replacement_targets = [target for target, count in Counter(str(row.get("replacement_for_blocked_row_id")) for row in replacements).items() if count > 1]

    bank: list[dict[str, Any]] = []
    for row in clean_old:
        enriched = dict(row)
        enriched["residual_successor_source"] = "stage11188_clean_old_reserved_row"
        bank.append(enriched)
    replacement_map: list[dict[str, Any]] = []
    for old in quarantined_old:
        old_id = str(old.get("row_id"))
        replacement = replacement_by_old.get(old_id)
        if not replacement:
            continue
        enriched = dict(replacement)
        enriched["residual_successor_source"] = "replacement_for_quarantined_reserved_row"
        enriched["replaces_quarantined_row_id"] = old_id
        bank.append(enriched)
        replacement_map.append({
            "old_row_id": old_id,
            "replacement_row_id": replacement.get("row_id"),
            "language_family": replacement.get("language_family"),
            "task_type": replacement.get("task_type"),
            "old_gold_value": gold_value(old),
            "replacement_gold_value": gold_value(replacement),
            "old_quarantine_reasons": (old.get("quarantine_card") or {}).get("reasons"),
        })

    root_ids = [str(row.get("root_id") or row.get("source_root_id") or row.get("row_id")) for row in bank]
    row_ids = [str(row.get("row_id")) for row in bank]
    anti_cheat_failures: list[dict[str, Any]] = []
    for row in bank:
        if row.get("residual_successor_source") == "stage11188_clean_old_reserved_row":
            continue
        anti = row.get("anti_cheat") or {}
        required = ["deterministic_option_shuffle", "gold_label_not_in_prompt_before_options", "target_role_not_named_as_answer_before_options", "visible_role_facts_are_distinct", "not_train_support", "replacement_for_quarantined_reserved_row"]
        missing_flags = [flag for flag in required if anti.get(flag) is not True]
        if missing_flags:
            anti_cheat_failures.append({"row_id": row.get("row_id"), "missing_flags": missing_flags})

    duplicate_root_clusters = {root: count for root, count in Counter(root_ids).items() if count > 1}
    # Legacy residual rows can share a root; that must be reported and scored cluster-aware,
    # but it should not block replacing the quarantined evidence rows when replacements are root-disjoint.
    replacement_root_ids = [
        str(row.get("root_id") or row.get("source_root_id") or row.get("row_id"))
        for row in bank
        if row.get("residual_successor_source") == "replacement_for_quarantined_reserved_row"
    ]
    replacement_duplicate_roots = {root: count for root, count in Counter(replacement_root_ids).items() if count > 1}
    passed = (
        not missing
        and not duplicate_replacement_targets
        and len(bank) == len(clean_old) + len(quarantined_old)
        and len(row_ids) == len(set(row_ids))
        and not replacement_duplicate_roots
        and not anti_cheat_failures
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": passed,
        "decision": "clean_residual_successor_bank_ready" if passed else "clean_residual_successor_bank_blocked",
        "promotion_eligible": passed,
        "source_artifacts": {
            "clean_old": rel(CLEAN_OLD),
            "quarantined_old": rel(QUARANTINED_OLD),
            "partial_replacements": rel(PARTIAL_REPLACEMENTS),
            "rust_replacements": rel(RUST_REPLACEMENTS),
        },
        "counts": {
            "clean_old_rows": len(clean_old),
            "quarantined_old_rows": len(quarantined_old),
            "replacement_rows": len(replacements),
            "successor_bank_rows": len(bank),
            "missing_replacements": len(missing),
            "duplicate_replacement_targets": len(duplicate_replacement_targets),
            "duplicate_row_ids": len(row_ids) - len(set(row_ids)),
            "duplicate_root_ids": len(root_ids) - len(set(root_ids)),
            "duplicate_root_clusters": duplicate_root_clusters,
            "replacement_duplicate_root_clusters": replacement_duplicate_roots,
            "root_clustered_independent_units": len(set(root_ids)),
            "anti_cheat_failures": len(anti_cheat_failures),
            "by_language_task": {f"{lang}::{task}": count for (lang, task), count in sorted(Counter(row_key(row) for row in bank).items())},
            "by_gold_value": dict(sorted(Counter(gold_value(row) for row in bank).items())),
            "by_source": dict(sorted(Counter(str(row.get("residual_successor_source")) for row in bank).items())),
        },
        "missing_replacements": [row.get("row_id") for row in missing],
        "duplicate_replacement_targets": duplicate_replacement_targets,
        "anti_cheat_failures": anti_cheat_failures,
        "outputs": {"summary_json": rel(SUMMARY_JSON), "bank_jsonl": rel(BANK_JSONL), "replacement_map_jsonl": rel(REPLACEMENT_MAP_JSONL)},
        "score_reporting_requirement": "Report row accuracy and root-clustered accuracy because two legacy clean rows share one root.",
        "next_best_step": "Score current 100M and Gemma on this clean residual successor bank under the productized scored-interface contract; do not train on these replacement rows first.",
    }
    write_jsonl(BANK_JSONL, bank)
    write_jsonl(REPLACEMENT_MAP_JSONL, replacement_map)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
