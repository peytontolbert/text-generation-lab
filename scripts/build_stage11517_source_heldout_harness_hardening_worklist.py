#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUM = ROOT / "runs/summaries"
NAME = "stage11517_source_heldout_harness_hardening_worklist"
OUT_DIR = ART / NAME
OUT_JSON = SUM / f"{NAME}.json"

SOURCE_INVENTORY = ART / "stage11469_source_heldout_harness_successor_inventory/source_heldout_harness_successor_inventory.json"
REPAIR_QUEUE = ART / "stage11469_source_heldout_harness_successor_inventory/source_heldout_harness_successor_repair_queue.jsonl"
ANTICHEAT = SUM / "stage11515_selected_frontier_anticheat_claim_audit.json"
HARDENED = SUM / "stage11516_selected_frontier_hardened_subset_comparison.json"
RESIDUAL50 = SUM / "stage11481_residual50_ready_package_with_rust_counters.json"

LANGUAGES = ("python", "rust", "c_cpp", "web_js_ts_html")
HARD_BLOCKERS = {
    "prompt_target_value_leak",
    "singleton_or_missing_options",
    "opaque_labels_not_confirmed",
    "missing_source_root",
}
REPAIRABLE_BLOCKERS = {
    "option_shuffle_not_declared",
    "missing_verifier_row_or_transition",
    "missing_patch_or_abstain_row",
    "not_source_heldout_admissible",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def blocker_score(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
    blockers = set(row.get("blockers") or [])
    hard = len(blockers & HARD_BLOCKERS)
    repairable = len(blockers & REPAIRABLE_BLOCKERS)
    has_verifier = int(bool(row.get("has_verifier_row_or_transition") or row.get("verifier_anchor") or row.get("selected_test_anchor")))
    has_patch = int(bool(row.get("has_patch_or_abstain_row")))
    return (hard, repairable, -has_verifier, -has_patch, str(row.get("row_id") or ""))


def main() -> None:
    inventory = load_json(SOURCE_INVENTORY)
    queue = read_jsonl(REPAIR_QUEUE)
    anticheat = load_json(ANTICHEAT)
    hardened = load_json(HARDENED)
    residual50 = load_json(RESIDUAL50)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    blocker_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    repo_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    task_counts_by_language: dict[str, Counter[str]] = defaultdict(Counter)
    source_heldout_candidate_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    nearest_rows: dict[str, list[dict[str, Any]]] = {}

    for row in queue:
        lang = str(row.get("language_family") or "unknown")
        by_language[lang].append(row)
        repo_counts_by_language[lang][str(row.get("repo_family") or "unknown")] += 1
        task_counts_by_language[lang][str(row.get("task_type") or "unknown")] += 1
        for blocker in row.get("blockers") or []:
            blocker_counts_by_language[lang][str(blocker)] += 1
        if row.get("source_heldout_admissible") is True:
            source_heldout_candidate_rows[lang].append(row)

    for lang in LANGUAGES:
        candidates = sorted(by_language.get(lang, []), key=blocker_score)
        nearest_rows[lang] = [
            {
                "row_id": row.get("row_id"),
                "source_root_id": row.get("source_root_id"),
                "repo_family": row.get("repo_family"),
                "task_type": row.get("task_type"),
                "blockers": row.get("blockers"),
                "selected_test_anchor": row.get("selected_test_anchor"),
                "verifier_anchor": row.get("verifier_anchor"),
                "has_verifier_row_or_transition": row.get("has_verifier_row_or_transition"),
                "has_patch_or_abstain_row": row.get("has_patch_or_abstain_row"),
                "deterministic_option_shuffle": row.get("deterministic_option_shuffle"),
                "prompt_target_value_leak": row.get("prompt_target_value_leak"),
                "source_heldout_admissible": row.get("source_heldout_admissible"),
                "source_file": row.get("source_file"),
            }
            for row in candidates[:25]
        ]

    work_items: list[dict[str, Any]] = []
    for lang in LANGUAGES:
        blockers = blocker_counts_by_language.get(lang, Counter())
        work_items.extend(
            [
                {
                    "language_family": lang,
                    "priority": 1,
                    "work_item": "materialize_or_attach_verifier_transition",
                    "why": "Stage11469 shows missing_verifier_row_or_transition dominates source-heldout successor blockers.",
                    "affected_rows": blockers.get("missing_verifier_row_or_transition", 0),
                    "acceptance": [
                        "selected_test_anchor=true or verifier_anchor=true",
                        "has_verifier_row_or_transition=true",
                        "verifier transition uses opaque test/verifier IDs before options",
                    ],
                },
                {
                    "language_family": lang,
                    "priority": 2,
                    "work_item": "repair_prompt_target_value_leaks",
                    "why": "Rows with direct target values before options cannot support anti-cheat claims.",
                    "affected_rows": blockers.get("prompt_target_value_leak", 0),
                    "acceptance": [
                        "gold option value absent from pre-options prompt text",
                        "semantic evidence preserved through opaque evidence IDs",
                    ],
                },
                {
                    "language_family": lang,
                    "priority": 3,
                    "work_item": "declare_and_verify_option_shuffle",
                    "why": "Stage11515 found deterministic_option_shuffle missing on most compact harness rows.",
                    "affected_rows": blockers.get("option_shuffle_not_declared", 0),
                    "acceptance": [
                        "deterministic_option_shuffle=true",
                        "same root can be rendered with at least two stable option orders for audit",
                    ],
                },
                {
                    "language_family": lang,
                    "priority": 4,
                    "work_item": "add_patch_or_abstain_rows",
                    "why": "The current harness writeback has no executable patch rows; broader full-product claims require patch/minimality evidence.",
                    "affected_rows": blockers.get("missing_patch_or_abstain_row", 0),
                    "acceptance": [
                        "has_patch_or_abstain_row=true",
                        "candidate patch/action has observable verifier consequence or explicit insufficient-evidence abstain",
                    ],
                },
            ]
        )

    promotion_requirements = {
        "minimal_smoke": {
            "rows": ">=1 hardened source-heldout row per language",
            "roots": ">=1 source-heldout root per language",
            "blocked_by_current_inventory": (inventory.get("metrics") or {}).get("minimal_successor_ready_one_row_per_language") is not True,
        },
        "promotion_candidate": {
            "rows": ">=12 hardened rows per language",
            "roots": ">=2 source-heldout roots per language",
            "gates": [
                "zero prompt_target_value_leak",
                "zero singleton_or_missing_options",
                "deterministic_option_shuffle=true",
                "opaque_labels=true",
                "selected_test_anchor or verifier_anchor present",
                "patch_or_abstain rows present for full-product claim",
                "same-manifest 100M and Gemma outputs attached",
                "100M beats Gemma overall and in all four language families",
            ],
        },
    }

    audit = {
        "stage": 11517,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "source_heldout_harness_hardening_worklist_ready",
        "current_frontier_context": {
            "compact_anticheat_passed": anticheat.get("passed"),
            "compact_hardened_subset_passed": hardened.get("passed"),
            "compact_hardened_subset_metrics": hardened.get("metrics"),
            "residual50_ready": residual50.get("passed"),
            "residual50_metrics": residual50.get("metrics"),
        },
        "source_heldout_inventory_metrics": inventory.get("metrics"),
        "repair_queue_summary": {
            "rows": len(queue),
            "by_language": {lang: len(by_language.get(lang, [])) for lang in LANGUAGES},
            "blockers_by_language": {
                lang: dict(sorted(blocker_counts_by_language.get(lang, Counter()).items()))
                for lang in LANGUAGES
            },
            "source_heldout_candidate_rows_by_language": {
                lang: len(source_heldout_candidate_rows.get(lang, [])) for lang in LANGUAGES
            },
            "top_repo_families_by_language": {
                lang: repo_counts_by_language.get(lang, Counter()).most_common(10) for lang in LANGUAGES
            },
            "task_counts_by_language": {
                lang: dict(sorted(task_counts_by_language.get(lang, Counter()).items()))
                for lang in LANGUAGES
            },
        },
        "nearest_repair_rows_by_language": nearest_rows,
        "work_items": sorted(work_items, key=lambda row: (row["priority"], row["language_family"])),
        "promotion_requirements": promotion_requirements,
        "claim_boundary": [
            "Stage11507/11516 supports a compact same-task maintainer-choice win over Gemma.",
            "Stage11517 does not claim the source-heldout/full-product successor is ready; it defines the required repair work to make that claim possible.",
        ],
        "outputs": {
            "work_items_jsonl": rel(OUT_DIR / "source_heldout_harness_hardening_work_items.jsonl"),
            "nearest_rows_json": rel(OUT_DIR / "nearest_repair_rows_by_language.json"),
        },
        "source_artifacts": {
            "source_inventory": rel(SOURCE_INVENTORY),
            "repair_queue": rel(REPAIR_QUEUE),
            "anticheat": rel(ANTICHEAT),
            "hardened_subset": rel(HARDENED),
            "residual50": rel(RESIDUAL50),
        },
        "next_best_step": "Materialize the minimal smoke successor: one source-heldout, option-shuffled, verifier-anchored row per language, then run 100M/Gemma same-manifest comparison under CUDA_VISIBLE_DEVICES=2.",
    }
    write_json(OUT_DIR / f"{NAME}.json", audit)
    write_json(OUT_DIR / "nearest_repair_rows_by_language.json", nearest_rows)
    write_jsonl(OUT_DIR / "source_heldout_harness_hardening_work_items.jsonl", audit["work_items"])
    write_json(OUT_JSON, audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
