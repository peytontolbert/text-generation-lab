#!/usr/bin/env python3
"""Rescore existing 100M strict row cards on the singleton-cleaned strict split."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11147_cleaned_strict_existing_runtime_rescore"
CLEAN_STRICT = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/agentkernel_lite_encdec_strict_eval.jsonl"
)
QUARANTINED = (
    ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/quarantined_singleton_strict_rows.jsonl"
)
STRICT_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage11133_evidence_item_option_probe/bounded_decoder_probe/bounded_choice_eval_audit_strict_eval.json"
)
RUNTIME_BUNDLE = (
    ROOT
    / "runs/local/artifacts/stage11133_evidence_item_option_probe/runtime_model/runtime_model_bundle.json"
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def group_accuracy(cards: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # The row cards do not carry language/task, so this function is used only
    # after metadata is joined in.
    for card in cards:
        groups[str(card.get(key))].append(card)
    out = {}
    for group, rows in groups.items():
        correct = sum(1 for r in rows if r.get("constrained_choice_match"))
        full = sum(1 for r in rows if r.get("full_vocab_top1_match"))
        out[group] = {
            "rows": len(rows),
            "constrained_correct": correct,
            "constrained_accuracy": correct / len(rows) if rows else 0.0,
            "full_vocab_correct": full,
            "full_vocab_accuracy": full / len(rows) if rows else 0.0,
        }
    return dict(sorted(out.items()))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clean_rows = read_jsonl(CLEAN_STRICT)
    quarantined_rows = read_jsonl(QUARANTINED) if QUARANTINED.exists() else []
    clean_ids = {row["row_id"] for row in clean_rows}
    meta_by_id = {row["row_id"]: row for row in clean_rows}
    audit = json.loads(STRICT_AUDIT.read_text())
    cards = audit.get("row_cards") or []
    card_by_id = {card.get("row_id"): card for card in cards}
    missing_cards = sorted(clean_ids - set(card_by_id))
    extra_cards = sorted(set(card_by_id) - clean_ids)

    filtered: list[dict[str, Any]] = []
    for row_id in sorted(clean_ids):
        card = dict(card_by_id[row_id])
        meta = meta_by_id[row_id]
        card.update(
            {
                "language_family": meta.get("language_family"),
                "task_type": meta.get("task_type"),
                "repo_family": meta.get("repo_family"),
                "source_root_id": meta.get("source_root_id"),
            }
        )
        filtered.append(card)

    constrained_correct = sum(1 for card in filtered if card.get("constrained_choice_match"))
    full_correct = sum(1 for card in filtered if card.get("full_vocab_top1_match"))
    mismatches = [card for card in filtered if not card.get("constrained_choice_match")]

    runtime = json.loads(RUNTIME_BUNDLE.read_text()) if RUNTIME_BUNDLE.exists() else {}
    summary = {
        "stage": 11147,
        "stage_name": "cleaned_strict_existing_runtime_rescore",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "clean_strict": str(CLEAN_STRICT.relative_to(ROOT)),
            "quarantined_singletons": str(QUARANTINED.relative_to(ROOT)),
            "strict_row_card_audit": str(STRICT_AUDIT.relative_to(ROOT)),
            "runtime_bundle": str(RUNTIME_BUNDLE.relative_to(ROOT)),
        },
        "runtime": {
            "weights_sha256": runtime.get("weights_sha256"),
            "source_stage": "stage11133_evidence_item_option_probe",
        },
        "metrics": {
            "strict_rows_original": audit.get("rows"),
            "strict_rows_cleaned": len(filtered),
            "quarantined_rows": len(quarantined_rows),
            "missing_clean_row_cards": missing_cards,
            "extra_original_row_cards_not_in_cleaned": extra_cards,
            "constrained_correct": constrained_correct,
            "constrained_accuracy": constrained_correct / len(filtered) if filtered else 0.0,
            "full_vocab_correct": full_correct,
            "full_vocab_accuracy": full_correct / len(filtered) if filtered else 0.0,
            "rows_with_target_rank_1": sum(1 for c in filtered if c.get("target_rank_full_vocab") == 1),
            "by_language": group_accuracy(filtered, "language_family"),
            "by_task_type": group_accuracy(filtered, "task_type"),
            "target_label_counts": dict(sorted(Counter(str(c.get("target_text")) for c in filtered).items())),
        },
        "mismatches": mismatches,
        "decision": "existing_runtime_rescored_on_cleaned_strict",
        "claim_scope": (
            "This is a rescore of existing stage11133 100M row cards after "
            "singleton strict quarantine. It is not a new training result and "
            "does not include a same-cleaned-split Gemma rerun."
        ),
        "outputs": {
            "filtered_row_cards_jsonl": str((OUT_DIR / "cleaned_strict_row_cards.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "cleaned_strict_existing_runtime_rescore.json").relative_to(ROOT)),
        },
    }

    with (OUT_DIR / "cleaned_strict_row_cards.jsonl").open("w") as f:
        for card in filtered:
            f.write(json.dumps(card, sort_keys=True) + "\n")
    (OUT_DIR / "cleaned_strict_existing_runtime_rescore.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
