#!/usr/bin/env python3
"""Audit stage11145 Python verifier candidates for ledger quality.

Target text appearing before options is not always leakage for verifier tasks:
if the prompt contains a verifier ledger listing every candidate target, the
model can legitimately choose the target whose transition is supported.  This
stage separates full-ledger rows from target-only leaks and broad, low-causal
test-list rows.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11151_python_verifier_candidate_ledger_audit"
ROWS_PATH = (
    ROOT
    / "runs/local/artifacts/stage11145_fresh_python_verifier_debiased_review_package/debiased_python_verifier_review_rows.jsonl"
)

LOW_SIGNAL_PHRASES = (
    "Changed file candidate:",
    "Task: Choose the visible python test or verifier consequence that best matches the evidence.",
)
TRANSITION_WORDS = (
    "FAIL_TO_PASS",
    "PASS_TO_PASS",
    "FAIL_TO_FAIL",
    "NOT_EXERCISED",
    "INCONCLUSIVE",
    "INSUFFICIENT",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def option_visibility(prompt_before_options: str, value: str) -> dict[str, Any]:
    value = str(value or "")
    basename = value.rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0]
    full_visible = bool(value and value in prompt_before_options)
    basename_visible = bool(basename and basename in prompt_before_options)
    stem_visible = bool(stem and len(stem) > 3 and stem in prompt_before_options)
    verifier_id = value.split("|", 1)[0].strip()
    verifier_id_visible = bool(
        verifier_id and re.fullmatch(r"[A-Z][0-9]+", verifier_id) and verifier_id in prompt_before_options
    )
    return {
        "value": value,
        "full_visible": full_visible,
        "basename_visible": basename_visible,
        "stem_visible": stem_visible,
        "verifier_id_visible": verifier_id_visible,
        "visible": full_visible or basename_visible or stem_visible or verifier_id_visible,
    }


def classify_row(row: dict[str, Any]) -> dict[str, Any]:
    prompt = str(row.get("input_text") or row.get("prompt_text") or "")
    before = prompt.split("\nOptions:\n", 1)[0]
    options = row.get("opaque_options") if isinstance(row.get("opaque_options"), list) else []
    target_label = str(row.get("target_text") or "")
    target_value = None
    vis = []
    for opt in options:
        if not isinstance(opt, dict):
            continue
        item = option_visibility(before, str(opt.get("value") or ""))
        item["label"] = str(opt.get("label"))
        vis.append(item)
        if str(opt.get("label")) == target_label:
            target_value = str(opt.get("value") or "")

    visible_count = sum(1 for item in vis if item["visible"])
    target_visible = any(item["label"] == target_label and item["visible"] for item in vis)
    non_target_visible = sum(1 for item in vis if item["label"] != target_label and item["visible"])
    all_options_visible = bool(vis) and visible_count == len(vis)
    transition_count = sum(1 for word in TRANSITION_WORDS if word in before)
    low_signal_hits = [phrase for phrase in LOW_SIGNAL_PHRASES if phrase in prompt]

    blockers: list[str] = []
    if len(options) < 3:
        blockers.append("insufficient_options")
    if target_visible and non_target_visible == 0:
        blockers.append("target_only_visible_before_options")
    if not all_options_visible:
        blockers.append("not_full_verifier_ledger")
    if transition_count == 0:
        blockers.append("missing_explicit_transition_semantics")
    if low_signal_hits:
        blockers.append("broad_changed_file_test_list_prompt")
    if "TODO_" in prompt or "PLACEHOLDER" in prompt:
        blockers.append("placeholder_text")

    if not blockers:
        admission = "admit_for_transition_review"
    elif blockers == ["broad_changed_file_test_list_prompt"]:
        admission = "diagnostic_only_low_signal"
    else:
        admission = "reject_or_requires_materialization"

    return {
        "row_id": row.get("row_id"),
        "source_root_id": row.get("source_root_id"),
        "source_bundle_id": row.get("source_bundle_id"),
        "repo_family": row.get("repo_family"),
        "target_label": target_label,
        "target_value": target_value,
        "option_count": len(options),
        "visible_option_count": visible_count,
        "all_options_visible_before_options": all_options_visible,
        "target_visible_before_options": target_visible,
        "non_target_visible_before_options": non_target_visible,
        "transition_word_count": transition_count,
        "low_signal_hits": low_signal_hits,
        "blockers": blockers,
        "admission": admission,
        "option_visibility": vis,
        "prompt_prefix": normalize(before)[:800],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(ROWS_PATH)
    cards = [classify_row(row) for row in rows]
    admission_counts = Counter(card["admission"] for card in cards)
    blocker_counts = Counter(blocker for card in cards for blocker in card["blockers"])
    label_counts = Counter(card["target_label"] for card in cards)
    admitted = [card for card in cards if card["admission"] == "admit_for_transition_review"]

    summary = {
        "stage": 11151,
        "stage_name": "python_verifier_candidate_ledger_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            "debiased_review_rows": str(ROWS_PATH.relative_to(ROOT)),
        },
        "metrics": {
            "rows_audited": len(cards),
            "admission_counts": dict(sorted(admission_counts.items())),
            "blocker_counts": dict(sorted(blocker_counts.items())),
            "target_label_counts": dict(sorted(label_counts.items())),
            "unique_roots": len({card["source_root_id"] for card in cards if card.get("source_root_id")}),
            "admitted_unique_roots": len({card["source_root_id"] for card in admitted if card.get("source_root_id")}),
        },
        "decision": (
            "candidate_rows_admitted_for_review"
            if admitted
            else "no_candidate_rows_admitted_for_review"
        ),
        "next_best_step": (
            "If no rows are admitted, build verifier-transition rows from real "
            "execution/test ledgers rather than broad changed-file/test-list candidates."
        ),
        "outputs": {
            "audit_cards_jsonl": str((OUT_DIR / "python_verifier_candidate_ledger_audit_cards.jsonl").relative_to(ROOT)),
            "admitted_review_cards_jsonl": str((OUT_DIR / "admitted_python_verifier_transition_review_cards.jsonl").relative_to(ROOT)),
            "summary_json": str((OUT_DIR / "python_verifier_candidate_ledger_audit.json").relative_to(ROOT)),
        },
    }

    with (OUT_DIR / "python_verifier_candidate_ledger_audit_cards.jsonl").open("w") as f:
        for card in cards:
            f.write(json.dumps(card, sort_keys=True) + "\n")
    with (OUT_DIR / "admitted_python_verifier_transition_review_cards.jsonl").open("w") as f:
        for card in admitted:
            f.write(json.dumps(card, sort_keys=True) + "\n")
    (OUT_DIR / "python_verifier_candidate_ledger_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
