#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10529
NAME = "stage10529_structured_projection_supply_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "structured_projection_supply_audit.json"
ENRICHED_ROWS_JSONL = OUT_DIR / "enriched_structured_projection_rows.jsonl"
SUMMARY_JSON = ROOT / "runs/summaries" / f"{NAME}.json"

MULTITARGET_ROWS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_multitarget_rows.jsonl"
ROOT_RECORDS = ROOT / "runs/local/artifacts/stage10516_long_context_root_state_compiler/compiled_root_records.jsonl"

STRUCTURED_SUBTYPES = {"next_action", "repair_intent", "patch_sketch", "verifier_outcome"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def contains_target_verbatim(row: dict[str, Any]) -> bool:
    input_text = str(row.get("input_text") or "")
    target_text = str(row.get("target_text") or "").strip()
    if not input_text or not target_text or len(target_text) < 8:
        return False
    return target_text in input_text


def enrich_row(row: dict[str, Any], root_meta: dict[str, Any] | None) -> dict[str, Any]:
    updated = dict(row)
    root_meta = root_meta or {}
    if root_meta:
        updated.setdefault("repo_id", root_meta.get("repo_id"))
        updated.setdefault("repo_family", root_meta.get("repo_family"))
        updated.setdefault("language_family", root_meta.get("language_family"))
        updated.setdefault("split_component", root_meta.get("split_component") or updated.get("split_component"))
        updated["environment_id"] = root_meta.get("environment_id")
        updated["snapshot_id"] = root_meta.get("snapshot_id")
        updated["verifier_id"] = root_meta.get("verifier_id")
        updated["task_family"] = root_meta.get("task_family")
    anti_cheat = dict(updated.get("anti_cheat") or {})
    anti_cheat["prompt_target_leak"] = contains_target_verbatim(updated)
    anti_cheat["prompt_target_leak_source"] = f"stage{STAGE}_visible_surface_recomputed"
    anti_cheat["same_root_train_eval_forbidden"] = True
    updated["anti_cheat"] = anti_cheat
    return updated


def main() -> None:
    rows = load_jsonl(MULTITARGET_ROWS)
    root_records = load_jsonl(ROOT_RECORDS)
    root_by_id = {str(row.get("root_id") or ""): row for row in root_records}

    structured_rows = [row for row in rows if str(row.get("target_subtype") or "") in STRUCTURED_SUBTYPES]
    enriched_rows = [enrich_row(row, root_by_id.get(str(row.get("root_id") or ""))) for row in structured_rows]
    write_jsonl(ENRICHED_ROWS_JSONL, enriched_rows)

    by_subtype = Counter(str(row.get("target_subtype") or "unknown") for row in enriched_rows)
    by_language_subtype: dict[str, Counter[str]] = defaultdict(Counter)
    by_split_subtype: dict[str, Counter[str]] = defaultdict(Counter)
    leakage_by_subtype: dict[str, int] = Counter()
    candidacy: dict[str, dict[str, Any]] = {}

    for row in enriched_rows:
        subtype = str(row.get("target_subtype") or "unknown")
        language = str(row.get("language_family") or "unknown")
        split = str(row.get("split_component") or "unknown")
        by_language_subtype[subtype][language] += 1
        by_split_subtype[subtype][split] += 1
        if ((row.get("anti_cheat") or {}).get("prompt_target_leak")) is True:
            leakage_by_subtype[subtype] += 1

    for subtype in sorted(by_subtype):
        total = by_subtype[subtype]
        leaks = int(leakage_by_subtype.get(subtype, 0))
        leak_rate = leaks / total if total else None
        split_counts = dict(sorted(by_split_subtype[subtype].items()))
        language_counts = dict(sorted(by_language_subtype[subtype].items()))
        if subtype == "verifier_outcome":
            recommendation = "reject_for_promotable_use"
            reason = "prompt_target_leak_dominates_current_surface"
        elif subtype == "patch_sketch":
            recommendation = "support_only_until_heldout_roots_exist"
            reason = "cleaner_surface_but_current_supply_is_train_only"
        elif subtype == "repair_intent":
            recommendation = "support_only_until_target_abstraction_is_hardened"
            reason = "long_text_target_repeats_changed_files_and_verification_targets"
        else:
            recommendation = "support_only"
            reason = "train_only_structured_projection"
        candidacy[subtype] = {
            "rows": total,
            "prompt_target_leak_rows": leaks,
            "prompt_target_leak_rate": leak_rate,
            "language_counts": language_counts,
            "split_counts": split_counts,
            "recommendation": recommendation,
            "reason": reason,
        }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "passed": True,
        "claim_scope": [
            "Audit and metadata backfill for long-context structured projection rows emitted by stage10516.",
            "This does not promote these rows into heldout scoring by itself.",
            "It identifies which structured target families are salvageable for future support or heldout expansion.",
        ],
        "structured_target_subtypes": dict(sorted(by_subtype.items())),
        "candidacy_by_subtype": candidacy,
        "global_findings": {
            "structured_rows_total": len(enriched_rows),
            "root_records_available": len(root_records),
            "language_backfill_succeeded_rows": sum(1 for row in enriched_rows if str(row.get("language_family") or "") != "unknown"),
            "repo_backfill_succeeded_rows": sum(1 for row in enriched_rows if str(row.get("repo_id") or "")),
        },
        "next_best_step": (
            "Do not use current verifier_outcome rows for promotable heldout scoring. "
            "Use the enriched patch_sketch/repair_intent/next_action rows as support-only structured curriculum, "
            "and build fresh non-leaky heldout roots for verifier_outcome and patch_sketch."
        ),
        "outputs": {
            "enriched_rows": str(ENRICHED_ROWS_JSONL.relative_to(ROOT)),
        },
    }
    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY_JSON, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
