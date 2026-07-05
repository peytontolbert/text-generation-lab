from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8902_diagnostic_promotion_gate import REQUIRED_PROMOTION_ARTIFACTS, promotion_gate_for_artifact_dir
from tests.test_native_probe_interpretability_artifact_contract import write_json, write_structured_artifacts


def test_structured_diagnostic_promotion_gate_accepts_complete_artifacts(tmp_path: Path) -> None:
    out = tmp_path / "structured"
    write_structured_artifacts(out)
    card = promotion_gate_for_artifact_dir(out, mode="structured_aux_probe")
    assert card["passed"] is True
    assert card["missing_required_artifacts"] == []
    assert card["promotion_ready"] is False


def test_structured_diagnostic_promotion_gate_rejects_decoder_delta(tmp_path: Path) -> None:
    out = tmp_path / "structured"
    write_structured_artifacts(out)
    write_json(out / "module_delta_norms.json", {"delta_norm_by_bucket": {"decoder": 0.1}, "decoder_delta_norm": 0.1, "total_delta_norm": 0.1})
    card = promotion_gate_for_artifact_dir(out, mode="structured_aux_probe")
    assert card["passed"] is False
    assert any("decoder" in error for error in card["errors"])


def test_diagnostic_promotion_gate_rejects_missing_artifact(tmp_path: Path) -> None:
    out = tmp_path / "structured"
    write_structured_artifacts(out)
    (out / "row_gradient_norms.jsonl").unlink()
    card = promotion_gate_for_artifact_dir(out, mode="structured_aux_probe")
    assert card["passed"] is False
    assert "row_gradient_norms.jsonl" in card["missing_required_artifacts"]


def test_required_promotion_artifact_lists_are_nonempty() -> None:
    assert "row_field_logits.jsonl" in REQUIRED_PROMOTION_ARTIFACTS["structured_aux_probe"]
    assert "row_token_loss.jsonl" in REQUIRED_PROMOTION_ARTIFACTS["bounded_decoder_ce_probe"]
