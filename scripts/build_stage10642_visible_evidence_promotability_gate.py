#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
STAGE = 10642
NAME = "stage10642_visible_evidence_promotability_gate"
PREVIEW_ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage10640_corrected_slice_visible_evidence_materialization_audit"
    / "corrected_slice_visible_evidence_materialized_preview_rows.jsonl"
)
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GATE_JSON = OUT_DIR / "visible_evidence_promotability_gate.json"
ADMITTED_JSONL = OUT_DIR / "visible_evidence_promotable_rows.jsonl"
BLOCKED_JSONL = OUT_DIR / "visible_evidence_blocked_rows.jsonl"

REAL_TEXT_KINDS = {"repo_span_text", "workspace_file_text"}
WEAK_KINDS = {"repo_summary_only", "paper_summary_only", "dataset_summary_only", "unknown_summary_only", "localchunk_summary_only", "localrepochunk_summary_only"}


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


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


def real_text_card_count(cards: list[dict[str, Any]]) -> int:
    return sum(1 for card in cards if str(card.get("resolution_kind") or "") in REAL_TEXT_KINDS and str(card.get("text") or "").strip())


def strongest_distractor_has_real_text(cards: list[dict[str, Any]], gold_label: str) -> bool:
    for card in cards:
        if str(card.get("label") or "") == gold_label:
            continue
        if str(card.get("resolution_kind") or "") in REAL_TEXT_KINDS and str(card.get("text") or "").strip():
            return True
    return False


def quality_flags(row: dict[str, Any]) -> dict[str, Any]:
    cards = list(row.get("cards") or [])
    gold_label = str(row.get("target_text") or "")
    gold_card = next((card for card in cards if str(card.get("label") or "") == gold_label), {})
    gold_kind = str(gold_card.get("resolution_kind") or "")
    real_count = real_text_card_count(cards)
    return {
        "gold_resolution_kind": gold_kind,
        "gold_has_real_text": gold_kind in REAL_TEXT_KINDS and bool(str(gold_card.get("text") or "").strip()),
        "real_text_card_count": real_count,
        "strongest_distractor_has_real_text": strongest_distractor_has_real_text(cards, gold_label),
        "all_cards_summary_only": all(str(card.get("resolution_kind") or "") in WEAK_KINDS for card in cards),
    }


def main() -> None:
    preview_rows = load_jsonl(PREVIEW_ROWS_PATH)
    admitted: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    for row in preview_rows:
        flags = quality_flags(row)
        reasons: list[str] = []
        if not flags["gold_has_real_text"]:
            reasons.append("gold_evidence_not_materialized_as_real_visible_text")
        if flags["real_text_card_count"] < 2:
            reasons.append("fewer_than_two_real_text_cards")
        if not flags["strongest_distractor_has_real_text"]:
            reasons.append("no_real_text_distractor_competition")
        if flags["all_cards_summary_only"]:
            reasons.append("all_cards_summary_only")

        projected = {
            "row_id": row["row_id"],
            "repo_id": row.get("repo_id"),
            "language_family": row.get("language_family"),
            "target_text": row.get("target_text"),
            "gold_handle": row.get("gold_handle"),
            "quality_flags": flags,
            "decision": "admit" if not reasons else "block",
            "reasons": reasons,
            "visible_prompt_text": row.get("visible_prompt_text"),
            "cards": row.get("cards"),
        }
        if reasons:
            blocked.append(projected)
        else:
            admitted.append(projected)

    admitted_by_lang = Counter(str(row.get("language_family") or "") for row in admitted)
    blocked_by_lang = Counter(str(row.get("language_family") or "") for row in blocked)
    blocked_reasons = Counter(reason for row in blocked for reason in row.get("reasons") or [])

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "decision": "strict_visible_evidence_gate_applied",
        "gate_contract": {
            "admit_if": [
                "gold evidence is materialized as real visible text",
                "at least two candidate cards have real visible text",
                "at least one non-gold distractor also has real visible text",
            ],
            "block_if": [
                "gold stays summary-only or handle-only",
                "candidate competition is mostly summary-only",
                "a maintainer would still need hidden handle knowledge to judge the row",
            ],
        },
        "metrics": {
            "input_rows": len(preview_rows),
            "admitted_rows": len(admitted),
            "blocked_rows": len(blocked),
            "admitted_by_language": dict(sorted(admitted_by_lang.items())),
            "blocked_by_language": dict(sorted(blocked_by_lang.items())),
            "blocked_reason_counts": dict(sorted(blocked_reasons.items())),
        },
        "claim_boundary": [
            "This gate is anti-cheat and source-quality enforcement only; it does not score any model.",
            "Rows admitted here are merely eligible for future maintainer review and exact-scored comparison, not automatically benchmark-ready.",
            "Rows blocked here should not be used for multilingual frontier claims until their evidence is truly materialized or rebuilt.",
        ],
        "next_best_step": [
            "Use admitted rows as the seed of a visible-evidence successor only if they also pass maintainer review.",
            "Rebuild or replace blocked rows from fresh roots or richer source inventories rather than training on them as if they were valid evidence-selection tasks.",
            "Keep the current reviewed v2.7 multilingual benchmark path separate from this transitional long-context slice until the blocked languages are replenished honestly.",
        ],
    }

    write_json(GATE_JSON, payload)
    write_jsonl(ADMITTED_JSONL, admitted)
    write_jsonl(BLOCKED_JSONL, blocked)
    print(
        json.dumps(
            {
                "ok": True,
                "gate": str(GATE_JSON),
                "admitted_rows": len(admitted),
                "blocked_rows": len(blocked),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
