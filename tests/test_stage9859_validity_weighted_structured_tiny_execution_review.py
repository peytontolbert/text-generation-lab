from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9859_validity_weighted_structured_tiny_execution_review.py"
    spec = importlib.util.spec_from_file_location("stage9695", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_cap_rows_limits_each_split():
    mod = _load()
    rows = []
    for split, count in {"train": 40, "eval": 20, "strict_eval": 18}.items():
        rows.extend({"row_id": f"{split}-{idx}", "split": split} for idx in range(count))
    capped = mod.cap_rows(rows)
    counts = {split: sum(1 for row in capped if row["split"] == split) for split in mod.CAPS}
    assert counts == mod.CAPS
    assert len(capped) == 64


def test_ticket_stays_inactive_and_requires_followup_contract():
    mod = _load()
    cards = []
    for surface, spec in mod.STRUCTURED_SURFACES.items():
        cards.append({
            "surface": surface,
            "manifest": str(mod.ROOT / f"runs/local/artifacts/x/{surface}.jsonl"),
            "rows": 64,
            "split_counts": {"train": 32, "eval": 16, "strict_eval": 16},
            "loss_counts": {spec["loss"]: 64},
            "expected_loss": spec["loss"],
            "authority": mod.AUTHORITY_CLOSED,
        })
    ticket = mod.build_ticket(cards)
    audit = mod.audit_ticket(ticket, {"passed": True}, cards)
    assert audit["passed"] is True
    assert ticket["execution_authorized_now"] is False
    assert ticket["allowed_operations_now"] == []
    assert "fresh_stage9860_capped_contract_only_preflight_passed" in ticket["required_before_execution"]
    assert "run_trainer" in ticket["denied_operations_now"]
