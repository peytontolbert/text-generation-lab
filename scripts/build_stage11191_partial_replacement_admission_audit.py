#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "runs/local/artifacts"
STAGE = 11191
NAME = "stage11191_partial_replacement_admission_audit"
OUT_DIR = ARTIFACTS / NAME
SUMMARY_JSON = OUT_DIR / "partial_replacement_admission_audit.json"
ROW_CARDS_JSONL = OUT_DIR / "partial_replacement_admission_cards.jsonl"
ADMITTED_ROWS_JSONL = OUT_DIR / "admitted_partial_replacement_rows.jsonl"
BLOCKED_ROWS_JSONL = OUT_DIR / "blocked_partial_replacement_rows.jsonl"

ROWS = ARTIFACTS / "stage11190_reserved_residual_partial_replacement_rows/replacement_strict_candidate_rows.jsonl"
TRAIN_ROWS = ARTIFACTS / "stage11178_contract_aware_evidence_rows/contract_aware_evidence_rows.jsonl"
STRICT_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
VALIDATION_ROWS = ARTIFACTS / "stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_validation.jsonl"
RESERVED_ROWS = ARTIFACTS / "stage11051_successor_residual_support_plus_priority_evidence/reserved_residual_candidates.jsonl"

REQUIRED_VALUES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
    "nearby_definition_or_usage_context",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def consumed_sets() -> dict[str, set[str]]:
    roots: set[str] = set()
    lineages: set[str] = set()
    source_rows: set[str] = set()
    repos: set[str] = set()
    for path in [TRAIN_ROWS, STRICT_ROWS, VALIDATION_ROWS, RESERVED_ROWS]:
        for row in load_jsonl(path):
            if row.get("root_id"):
                roots.add(str(row.get("root_id")))
            if row.get("source_root_id"):
                roots.add(str(row.get("source_root_id")))
            if row.get("root_lineage_key"):
                lineages.add(str(row.get("root_lineage_key")))
            if row.get("source_retrieval_row_id"):
                source_rows.add(str(row.get("source_retrieval_row_id")))
            if row.get("repo_family"):
                repos.add(str(row.get("repo_family")))
    return {"roots": roots, "lineages": lineages, "source_rows": source_rows, "repos": repos}


def audit_row(row: dict[str, Any], consumed: dict[str, set[str]]) -> dict[str, Any]:
    blockers: list[str] = []
    options = row.get("opaque_options") or []
    values = [str(opt.get("value")) for opt in options]
    labels = [str(opt.get("label")) for opt in options]
    source = row.get("standalone_projection_source") or {}
    gold_value = str(source.get("gold_value") or "")
    gold_label = str(source.get("gold_label") or row.get("target_text") or "")
    pre_options = str(row.get("input_text") or "").split("Options:", 1)[0]
    role_paths = source.get("role_paths") or {}

    if set(values) != REQUIRED_VALUES:
        blockers.append("option_values_not_exact_required_set")
    if len(labels) != len(set(labels)) or len(labels) != 4:
        blockers.append("option_labels_not_unique_four_way")
    if gold_value not in values:
        blockers.append("gold_value_missing_from_options")
    if gold_label not in labels:
        blockers.append("gold_label_missing_from_options")
    if gold_label and re.search(rf"(?m)^\s*{re.escape(gold_label)}[.)]\s+", pre_options):
        blockers.append("gold_label_leaks_before_options")
    if gold_value and gold_value in pre_options:
        blockers.append("gold_value_leaks_before_options")
    anti = row.get("anti_cheat") or {}
    for flag in [
        "deterministic_option_shuffle",
        "gold_label_not_in_prompt_before_options",
        "target_role_not_named_as_answer_before_options",
        "visible_role_facts_are_distinct",
        "not_train_support",
        "replacement_for_quarantined_reserved_row",
    ]:
        if anti.get(flag) is not True:
            blockers.append(f"anti_cheat_flag_false::{flag}")
    role_sets = {role: set(paths or []) for role, paths in role_paths.items()}
    for role in ["candidate_change_surface", "verifier_and_test_constraint", "symptom_or_call_path_analogue"]:
        if not role_sets.get(role):
            blockers.append(f"missing_role_paths::{role}")
    if role_sets.get("candidate_change_surface", set()) & role_sets.get("verifier_and_test_constraint", set()):
        blockers.append("candidate_verifier_path_overlap")
    if role_sets.get("candidate_change_surface", set()) & role_sets.get("symptom_or_call_path_analogue", set()):
        blockers.append("candidate_symptom_path_overlap")
    if row.get("root_id") in consumed["roots"]:
        blockers.append("root_id_overlaps_consumed")
    if row.get("root_lineage_key") in consumed["lineages"]:
        blockers.append("root_lineage_overlaps_consumed")
    if row.get("source_retrieval_row_id") in consumed["source_rows"]:
        blockers.append("source_retrieval_row_overlaps_consumed")
    if not row.get("replacement_for_blocked_row_id"):
        blockers.append("missing_replacement_for_blocked_row_id")

    return {
        "row_id": row.get("row_id"),
        "admitted": not blockers,
        "blockers": blockers,
        "language_family": row.get("language_family"),
        "repo_family": row.get("repo_family"),
        "gold_value": gold_value,
        "target_label": row.get("target_text"),
        "source_retrieval_row_id": row.get("source_retrieval_row_id"),
        "replacement_for_blocked_row_id": row.get("replacement_for_blocked_row_id"),
    }


def main() -> None:
    rows = load_jsonl(ROWS)
    consumed = consumed_sets()
    cards = [audit_row(row, consumed) for row in rows]
    admitted_ids = {card["row_id"] for card in cards if card["admitted"]}
    admitted = [row for row in rows if row.get("row_id") in admitted_ids]
    blocked = [row for row in rows if row.get("row_id") not in admitted_ids]
    blocker_counts = Counter(reason for card in cards for reason in card["blockers"])
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": len(blocked) == 0 and len(admitted) == len(rows),
        "decision": "partial_replacement_rows_admitted" if len(blocked) == 0 else "partial_replacement_rows_blocked",
        "promotion_eligible": False,
        "reason_not_promotion_eligible": "Only 3 of 6 quarantined residual evidence rows have replacements; Rust slots remain absent.",
        "source_artifacts": {
            "candidate_rows": rel(ROWS),
            "train_rows": rel(TRAIN_ROWS),
            "strict_rows": rel(STRICT_ROWS),
            "validation_rows": rel(VALIDATION_ROWS),
            "reserved_rows": rel(RESERVED_ROWS),
        },
        "counts": {
            "input_rows": len(rows),
            "admitted_rows": len(admitted),
            "blocked_rows": len(blocked),
            "by_language": dict(sorted(Counter(str(row.get("language_family")) for row in admitted).items())),
            "by_gold_value": dict(sorted(Counter(str((row.get("standalone_projection_source") or {}).get("gold_value")) for row in admitted).items())),
            "blocker_counts": dict(sorted(blocker_counts.items())),
        },
        "outputs": {
            "summary_json": rel(SUMMARY_JSON),
            "row_cards_jsonl": rel(ROW_CARDS_JSONL),
            "admitted_rows_jsonl": rel(ADMITTED_ROWS_JSONL),
            "blocked_rows_jsonl": rel(BLOCKED_ROWS_JSONL),
        },
        "next_best_step": "Mine/materialize fresh Rust evidence replacement rows, then combine admitted replacements into a clean residual successor bank before any probe.",
    }
    write_jsonl(ROW_CARDS_JSONL, cards)
    write_jsonl(ADMITTED_ROWS_JSONL, admitted)
    write_jsonl(BLOCKED_ROWS_JSONL, blocked)
    write_json(SUMMARY_JSON, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
