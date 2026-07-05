from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8903_diagnostics_closure_audit import AUTHORITY_CLOSED, CLOSURE_DIMENSIONS, STILL_REQUIRES_REAL_RUN_ARTIFACTS, closure_audit


def registry(latest: int = 8902) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_closure_dimensions_cover_core_diagnostics() -> None:
    assert "row_field_logits_confidence_entropy" in CLOSURE_DIMENSIONS
    assert "row_gradient_norms" in CLOSURE_DIMENSIONS
    assert "activation_summaries" in CLOSURE_DIMENSIONS
    assert "feature_ablation_attribution" in CLOSURE_DIMENSIONS
    assert "promotion_blocker" in CLOSURE_DIMENSIONS


def test_closure_explicitly_requires_real_run_artifacts_for_claims() -> None:
    assert "actual_row_field_logits_jsonl" in STILL_REQUIRES_REAL_RUN_ARTIFACTS
    assert "actual_row_token_loss_jsonl_for_decoder_claims" in STILL_REQUIRES_REAL_RUN_ARTIFACTS


def test_closure_audit_keeps_authority_closed() -> None:
    card = closure_audit(registry())
    assert card["registry_authority_counts_zero"] is True
    assert card["registry_latest_stage_before_update"] == 8902


def test_closure_audit_rejects_unexpected_frontier() -> None:
    card = closure_audit(registry(latest=9999))
    assert card["passed"] is False
    assert "unexpected_registry_frontier:9999" in card["failures"]
