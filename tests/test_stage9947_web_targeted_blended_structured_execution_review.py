from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9947_web_targeted_blended_structured_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9947", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build_surface_cards_preserves_web_recovery_rows():
    mod = _load()
    cards = mod.build_surface_cards()
    edit_card = next(card for card in cards if card["surface"] == "edit_localization")
    assert sum(card["rows"] for card in cards) == 404
    assert edit_card["rows"] == 72
    assert edit_card["language_counts"]["web_js_ts_html"] == 27
    assert edit_card["loss_counts"] == {"edit_localization_ce": 72}


def test_ticket_stays_inactive_and_requires_blended_contract_followup():
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
    cards[1]["language_counts"] = {"python": 20, "web_js_ts_html": 27}
    cards[1]["rows"] = 47
    cards[1]["loss_counts"] = {"edit_localization_ce": 47}
    cards[1]["split_counts"] = {"train": 15, "eval": 16, "strict_eval": 16, "other": 0}
    blend_audit = {
        "passed": True,
        "metrics": {
            "base_structured_rows": 392,
            "blended_structured_rows": 77,
            "targeted_web_rows_added": 12,
            "targeted_web_weight_sum": 30,
            "web_edit_rows_before": 15,
            "web_edit_rows_after": 27,
        },
    }
    ticket = mod.build_ticket(cards, blend_audit)
    audit = mod.audit_ticket(ticket, {"passed": True}, blend_audit, cards)
    assert audit["passed"] is True
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert "fresh_stage9946_blended_contract_only_preflight_passed" in ticket["required_before_execution"]
    assert ticket["blend_context"]["targeted_web_rows_added"] == 12
    assert ticket["blend_context"]["edit_localization_web_rows_in_review_manifest"] == 27
