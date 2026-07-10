from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9964_blended_weak_language_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9964", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_surface_cards_preserves_successor_recovery_rows():
    mod = _load()
    cards = mod.build_surface_cards()
    edit_card = next(card for card in cards if card["surface"] == "edit_localization")
    assert sum(card["rows"] for card in cards) == 452
    assert edit_card["rows"] == 120
    assert edit_card["language_counts"]["web_js_ts_html"] == 45
    assert edit_card["language_counts"]["python"] == 24
    assert edit_card["language_counts"]["c_cpp"] == 30
    assert edit_card["loss_counts"] == {"edit_localization_ce": 120}


def test_ticket_stays_inactive_and_requires_successor_contract_followup():
    mod = _load()
    cards = []
    for surface, spec in mod.STRUCTURED_SURFACES.items():
        cards.append({
            "surface": surface,
            "manifest": f"runs/local/artifacts/mock/{surface}.jsonl",
            "source_manifest": f"runs/local/artifacts/source/{surface}.jsonl",
            "rows": 10,
            "split_counts": {"train": 4, "eval": 3, "strict_eval": 3, "other": 0},
            "loss_counts": {spec["loss"]: 10},
            "expected_loss": spec["loss"],
            "language_counts": {"python": 10},
            "authority": mod.AUTHORITY_CLOSED,
        })
    cards[1]["language_counts"] = {"python": 24, "c_cpp": 30, "rust": 21, "web_js_ts_html": 45}
    cards[1]["rows"] = 120
    cards[1]["loss_counts"] = {"edit_localization_ce": 120}
    cards[1]["split_counts"] = {"train": 40, "eval": 40, "strict_eval": 40, "other": 0}
    blend_audit = {
        "passed": True,
        "metrics": {
            "base_structured_rows": 404,
            "blended_structured_rows": 150,
            "recovery_rows_added": 48,
            "recovery_weight_sum": 147,
            "python_edit_rows_after": 24,
            "c_cpp_edit_rows_after": 30,
            "rust_edit_rows_after": 21,
            "web_edit_rows_after": 45,
        },
    }
    ticket = mod.build_ticket(cards, blend_audit)
    audit = mod.audit_ticket(ticket, {"passed": True}, blend_audit, cards)
    assert audit["passed"] is True
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert "fresh_stage9963_blended_contract_only_preflight_passed" in ticket["required_before_execution"]
    assert ticket["blend_context"]["recovery_rows_added"] == 48
    assert ticket["blend_context"]["edit_localization_web_rows_in_review_manifest"] == 45
