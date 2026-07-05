from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from adversarial_hard_negative_generator import ATTACK_TYPES, audit_hard_negatives, generate_hard_negatives, hard_negative_card


def seed_row() -> dict:
    return {
        "row_id": "seed",
        "objective_family": "symbol_binding",
        "semantic_key": "symbol:x",
        "corrupted_state": {"language": "python", "evidence": "source span", "source_excerpt": "def x(): pass"},
    }


def test_generates_all_attack_types_per_seed() -> None:
    rows = generate_hard_negatives([seed_row()])
    attacks = {row["adversarial"]["attack_type"] for row in rows}
    assert attacks == set(ATTACK_TYPES)
    assert len(rows) == len(ATTACK_TYPES)


def test_hard_negatives_never_enable_authority_or_losses() -> None:
    rows = generate_hard_negatives([seed_row()])
    audit = audit_hard_negatives(rows)
    assert audit["passed"] is True
    assert audit["authority_rows"] == 0
    assert audit["loss_enabled_rows"] == 0
    assert audit["decode_enabled_rows"] == 0


def test_evidence_removed_marks_missing_evidence() -> None:
    rows = generate_hard_negatives([seed_row()], attacks=["EVIDENCE_REMOVED"])
    row = rows[0]
    assert row["missing_evidence"] is True
    assert row["corrupted_state"]["evidence_state"] == "removed"
    assert "source_excerpt" not in row["corrupted_state"]


def test_leak_injection_adds_leak_probe_text() -> None:
    rows = generate_hard_negatives([seed_row()], attacks=["LEAK_INJECTION"])
    row = rows[0]
    assert row["internal_leak"] is True
    assert "expected_answer" in row["corrupted_state"]["poisoned_visible_text"]


def test_card_counts_seed_and_generated_rows() -> None:
    card = hard_negative_card([seed_row(), {**seed_row(), "row_id": "seed2"}])
    assert card["seed_rows"] == 2
    assert card["generated_rows"] == 2 * len(ATTACK_TYPES)
    assert card["audit"]["passed"] is True
    assert card["authority"]["training_authorized_next"] is False
