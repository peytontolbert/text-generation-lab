from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8971_trainer_contract_reconciliation_no_execution import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_FLAGS,
    REQUIRED_MODES,
    REQUIRED_TELEMETRY_TERMS,
    validate_card,
)


def registry(latest: int = 8970) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "trainer_contract_only_invoked": False,
            "model_execution_attempted": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
    }


def test_stage8971_required_flags_cover_probe_safety_surface() -> None:
    for flag in ["--manifest", "--mode", "--require-loss-mask-enforcement-audit", "--no-final-checkpoint-export", "--cleanup-checkpoints-after-probe", "--contract-only"]:
        assert flag in REQUIRED_FLAGS


def test_stage8971_required_modes_cover_maintainer_spine() -> None:
    for mode in ["symbol_binding_probe", "edit_localization_probe", "patch_operator_probe", "verifier_repair_probe", "bounded_decoder_ce_probe", "denoise_repair_probe"]:
        assert mode in REQUIRED_MODES


def test_stage8971_telemetry_terms_include_interpretability_artifacts() -> None:
    for term in ["row_gradient_norms.jsonl", "activation_summary.jsonl", "feature_ablation_attribution.jsonl", "activation_patch_recovery.jsonl", "module_delta_norms.json"]:
        assert term in REQUIRED_TELEMETRY_TERMS


def test_stage8971_validation_rejects_execution_or_bad_frontier() -> None:
    assert validate_card(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "model_execution_attempted": True}
    assert "model_execution_attempted" in validate_card(bad, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(base_card(), registry(9999))
