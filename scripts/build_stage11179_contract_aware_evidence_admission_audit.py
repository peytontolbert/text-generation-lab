#!/usr/bin/env python3
"""Audit stage11178 contract-aware evidence rows before training use."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IN_DIR = ROOT / "runs/local/artifacts/stage11178_contract_aware_evidence_rows"
OUT_DIR = ROOT / "runs/local/artifacts/stage11179_contract_aware_evidence_admission_audit"
REQUIRED_ROLES = {
    "candidate_change_surface",
    "verifier_and_test_constraint",
    "symptom_or_call_path_analogue",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def prompt_before_options(row: dict[str, Any]) -> str:
    text = str(row.get("input_text") or "")
    return text.split("\nOptions:", 1)[0]


def option_values(row: dict[str, Any]) -> list[str]:
    return [str(opt.get("value")) for opt in row.get("opaque_options") or [] if isinstance(opt, dict)]


def gold_value(row: dict[str, Any]) -> str:
    return str((row.get("standalone_projection_source") or {}).get("gold_value") or "")


def evidence_facts(row: dict[str, Any]) -> dict[str, str]:
    return {
        str(k): str(v)
        for k, v in ((row.get("standalone_projection_source") or {}).get("evidence_facts") or {}).items()
    }


def row_card(row: dict[str, Any]) -> dict[str, Any]:
    gold = gold_value(row)
    options = option_values(row)
    facts = evidence_facts(row)
    before = prompt_before_options(row)
    blockers: list[str] = []

    if gold not in REQUIRED_ROLES:
        blockers.append("gold_role_not_required_training_role")
    if gold not in options:
        blockers.append("gold_value_missing_from_options")
    if len(set(options)) != len(options):
        blockers.append("duplicate_option_values")
    missing_roles = sorted(REQUIRED_ROLES - set(facts))
    if missing_roles:
        blockers.append("missing_required_evidence_facts")
    fact_values = [value for key, value in facts.items() if key in REQUIRED_ROLES]
    if len(set(fact_values)) != len(fact_values):
        blockers.append("duplicate_evidence_fact_text")
    if gold in before:
        blockers.append("gold_role_name_visible_before_options")
    # Opaque labels are single characters, so substring checks are meaningless
    # here; the materializer never prints the answer label before the options.
    if not ((row.get("anti_cheat") or {}).get("deterministic_option_shuffle")):
        blockers.append("missing_deterministic_option_shuffle_flag")
    if row.get("strict_eval_eligible"):
        blockers.append("strict_eval_eligible_should_be_false")

    return {
        "row_id": row.get("row_id"),
        "root_id": row.get("root_id"),
        "repo_family": row.get("repo_family"),
        "language_family": row.get("language_family"),
        "gold_value": gold,
        "target_text": row.get("target_text"),
        "option_values": options,
        "blockers": blockers,
        "admitted": not blockers,
    }


def main() -> None:
    rows = load_jsonl(IN_DIR / "contract_aware_evidence_rows.jsonl")
    blocked_source = load_jsonl(IN_DIR / "blocked_evidence_materialization_rows.jsonl")
    cards = [row_card(row) for row in rows]
    admitted_cards = [card for card in cards if card["admitted"]]
    failed_cards = [card for card in cards if not card["admitted"]]

    role_counts = Counter(card["gold_value"] for card in admitted_cards)
    language_counts = Counter(str(card["language_family"]) for card in admitted_cards)
    by_language_role: dict[str, dict[str, int]] = defaultdict(dict)
    for (language, role), count in Counter((str(card["language_family"]), card["gold_value"]) for card in admitted_cards).items():
        by_language_role[language][role] = count

    blocker_counts = Counter(reason for card in failed_cards for reason in card["blockers"])
    source_blocker_counts = Counter(reason for card in blocked_source for reason in card.get("blockers", []))
    required_role_floor = min((role_counts.get(role, 0) for role in REQUIRED_ROLES), default=0)
    language_with_all_roles = {
        language: all(by_language_role[language].get(role, 0) > 0 for role in REQUIRED_ROLES)
        for language in sorted(language_counts)
    }

    train_admission_passed = (
        len(admitted_cards) == len(rows)
        and required_role_floor >= 20
        and all(language_with_all_roles.values())
        and not failed_cards
    )

    summary = {
        "stage": 11179,
        "created_at": now_utc(),
        "input_rows": rel(IN_DIR / "contract_aware_evidence_rows.jsonl"),
        "source_blocked_rows": rel(IN_DIR / "blocked_evidence_materialization_rows.jsonl"),
        "admitted_rows": len(admitted_cards),
        "failed_materialized_rows": len(failed_cards),
        "source_blocked_rows_count": len(blocked_source),
        "gold_value_counts": dict(sorted(role_counts.items())),
        "language_counts": dict(sorted(language_counts.items())),
        "by_language_role_counts": {k: dict(sorted(v.items())) for k, v in sorted(by_language_role.items())},
        "materialized_blocker_counts": dict(sorted(blocker_counts.items())),
        "source_blocker_counts": dict(sorted(source_blocker_counts.items())),
        "required_role_floor": required_role_floor,
        "language_with_all_required_roles": language_with_all_roles,
        "train_admission_passed": train_admission_passed,
        "promotion_eligible": False,
        "decision": "train_support_admitted" if train_admission_passed else "needs_language_or_source_replenishment",
        "notes": [
            "This audit admits train-support rows only; it does not create strict/eval rows.",
            "The package is role-balanced globally but should not be used for a multilingual evidence claim unless each language has role coverage.",
            "Blocked source rows identify where source materialization, not training, remains the bottleneck.",
        ],
        "outputs": {
            "row_cards": rel(OUT_DIR / "contract_aware_evidence_admission_cards.jsonl"),
            "summary": rel(OUT_DIR / "contract_aware_evidence_admission_audit.json"),
        },
    }

    write_jsonl(OUT_DIR / "contract_aware_evidence_admission_cards.jsonl", cards)
    write_json(OUT_DIR / "contract_aware_evidence_admission_audit.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
