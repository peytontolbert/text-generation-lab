#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"

STAGE = 11470
NAME = "stage11470_harness_successor_materialization_request"
OUT = ART / NAME
SUMMARY = OUT / "harness_successor_materialization_request.json"
WORK_ITEMS = OUT / "harness_successor_materialization_work_items.jsonl"

INVENTORY = ART / "stage11469_source_heldout_harness_successor_inventory/source_heldout_harness_successor_inventory.json"
REPAIR_QUEUE = ART / "stage11469_source_heldout_harness_successor_inventory/source_heldout_harness_successor_repair_queue.jsonl"

LANGUAGES = ("python", "rust", "c_cpp", "web_js_ts_html")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def sample(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    out = []
    seen_roots = set()
    for row in rows:
        key = (row.get("source_root_id"), row.get("repo_family"), row.get("task_type"))
        if key in seen_roots:
            continue
        seen_roots.add(key)
        out.append(
            {
                "row_id": row.get("row_id"),
                "language_family": row.get("language_family"),
                "task_type": row.get("task_type"),
                "repo_family": row.get("repo_family"),
                "source_root_id": row.get("source_root_id"),
                "source_file": row.get("source_file"),
                "blockers": row.get("blockers"),
            }
        )
        if len(out) >= limit:
            break
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = load_json(INVENTORY)
    rows = load_jsonl(REPAIR_QUEUE)

    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_language[str(row.get("language_family") or "")].append(row)

    source_heldout = [row for row in rows if row.get("source_heldout_admissible")]
    source_heldout_by_lang = defaultdict(list)
    for row in source_heldout:
        source_heldout_by_lang[str(row.get("language_family") or "")].append(row)

    has_verifier_by_lang = defaultdict(list)
    for row in rows:
        if row.get("has_verifier_row_or_transition"):
            has_verifier_by_lang[str(row.get("language_family") or "")].append(row)

    no_leak_multi_by_lang = defaultdict(list)
    for row in rows:
        if not row.get("prompt_target_value_leak") and int(row.get("option_count") or 0) > 1:
            no_leak_multi_by_lang[str(row.get("language_family") or "")].append(row)

    work_items: list[dict[str, Any]] = []

    for language in LANGUAGES:
        current_source_heldout = source_heldout_by_lang.get(language, [])
        if not current_source_heldout:
            work_items.append(
                {
                    "work_item_id": f"{NAME}::{language}::fresh_source_heldout_roots_required",
                    "priority": "P0",
                    "language_family": language,
                    "action": "materialize_fresh_source_heldout_roots",
                    "reason": "Stage11469 found zero source_heldout_admissible rows for this language.",
                    "minimum_output": {
                        "root_count": 2,
                        "rows_per_root": "at least verifier_outcome, evidence_citation, patch_impact_or_abstain",
                        "required_fields": [
                            "source_heldout_admissible=true",
                            "source_root_id",
                            "selected_test_anchor for verifier/evidence rows",
                            "verifier_row",
                            "patch_row or explicit abstain scoring row",
                            "opaque_options with option_count > 1",
                            "anti_cheat.deterministic_option_shuffle=true after actual shuffle",
                            "prompt_target_value_leak=false",
                        ],
                    },
                    "near_miss_examples": sample(no_leak_multi_by_lang.get(language, []), 4),
                }
            )
        else:
            blockers = Counter(blocker for row in current_source_heldout for blocker in row.get("blockers", []))
            work_items.append(
                {
                    "work_item_id": f"{NAME}::{language}::repair_existing_source_heldout_rows",
                    "priority": "P0" if language == "rust" else "P1",
                    "language_family": language,
                    "action": "repair_existing_source_heldout_rows",
                    "reason": "Source-heldout rows exist but fail harness successor gates.",
                    "source_heldout_rows": len(current_source_heldout),
                    "top_blockers": dict(blockers.most_common()),
                    "minimum_output": {
                        "root_count": 2,
                        "required_fixes": [
                            "fill source_root_id where missing using row_id/source_bundle_id lineage",
                            "attach selected test/verifier logs",
                            "add verifier_row objects with transition semantics",
                            "add patch_row or explicit abstain scoring rows",
                            "rewrite prompts to remove target path/value leakage before Options",
                            "shuffle options deterministically and set anti_cheat.deterministic_option_shuffle=true",
                        ],
                    },
                    "candidate_rows": sample(current_source_heldout, 12),
                }
            )

    work_items.append(
        {
            "work_item_id": f"{NAME}::global::harness_row_contract_patch",
            "priority": "P0",
            "language_family": "all",
            "action": "patch_row_builders_for_harness_successor_contract",
            "reason": "Stage11469 found broad schema gaps independent of source supply.",
            "required_contract": {
                "row_level": [
                    "source_heldout_admissible",
                    "source_root_id",
                    "anti_cheat.deterministic_option_shuffle",
                    "opaque_options",
                    "verifier_row for verifier/evidence rows",
                    "patch_row or abstain_score_row for patch/minimal-fix/abstention rows",
                ],
                "packet_level": [
                    "at least two source roots per language",
                    "no singleton options",
                    "no target value before Options",
                    "selected-test anchored web rows",
                    "non-singleton Rust verifier rows",
                ],
            },
        }
    )

    metrics = dict(inventory.get("metrics") or {})
    materialization_ready = False
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "materialization_required_before_successor_harness_probe",
        "materialization_ready": materialization_ready,
        "inventory_metrics": metrics,
        "work_item_count": len(work_items),
        "work_items_by_language": dict(Counter(str(item["language_family"]) for item in work_items)),
        "blocking_summary": {
            "admitted_rows_now": metrics.get("admitted_rows"),
            "source_heldout_rows_by_language": metrics.get("source_heldout_rows_by_language"),
            "top_blockers": metrics.get("top_blockers"),
        },
        "next_stage_recommendation": (
            "Build stage11471 by repairing the Rust Candle source-heldout rows and materializing at least one fresh source-heldout "
            "Python/C++/web root each with verifier_row plus patch_or_abstain scoring rows. Do not train or rerun harness promotion until "
            "Stage11469 admits a nonzero successor set."
        ),
        "source_artifacts": {
            "inventory": rel(INVENTORY),
            "repair_queue": rel(REPAIR_QUEUE),
        },
        "outputs": {
            "summary": rel(SUMMARY),
            "work_items": rel(WORK_ITEMS),
        },
    }
    write_jsonl(WORK_ITEMS, work_items)
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(json.dumps({"decision": summary["decision"], "work_item_count": len(work_items), "blocking_summary": summary["blocking_summary"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
