from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mixed_precision_runtime_contract import (
    MixedPrecisionRequest,
    build_precision_policy_card,
    estimate_memory_mb,
    safe_default_policy,
    validate_mixed_precision_request,
)


def test_safe_default_policy_is_fp32_and_closed_authority() -> None:
    card = safe_default_policy()
    assert card["passed"] is True
    assert card["request"]["precision"] == "fp32"
    assert card["authority"]["model_execution"] is False
    assert card["authority"]["training"] is False


def test_fp16_training_requires_grad_scaler() -> None:
    card = validate_mixed_precision_request(
        MixedPrecisionRequest(precision="fp16", device="cuda", use_autocast=True, training_authorized=True)
    )
    assert card["passed"] is False
    assert "fp16 training requires GradScaler" in card["errors"]


def test_bf16_rejects_grad_scaler() -> None:
    card = validate_mixed_precision_request(
        MixedPrecisionRequest(precision="bf16", device="cuda", use_autocast=True, use_grad_scaler=True)
    )
    assert card["passed"] is False
    assert "bf16 should not use GradScaler" in card["errors"]


def test_mixed_precision_execution_requires_autocast_when_authorized() -> None:
    card = validate_mixed_precision_request(
        MixedPrecisionRequest(precision="bf16", device="cuda", model_execution_authorized=True)
    )
    assert card["passed"] is False
    assert "mixed precision execution requires autocast" in card["errors"]


def test_memory_estimate_tracks_precision_and_activation_checkpointing() -> None:
    fp32 = estimate_memory_mb(parameter_count=1000, sequence_tokens=100, hidden_dim=64, batch_size=2, precision="fp32")
    bf16 = estimate_memory_mb(parameter_count=1000, sequence_tokens=100, hidden_dim=64, batch_size=2, precision="bf16")
    ckpt = estimate_memory_mb(parameter_count=1000, sequence_tokens=100, hidden_dim=64, batch_size=2, precision="bf16", activation_checkpointing=True)
    assert bf16["parameter_mb"] == fp32["parameter_mb"] / 2
    assert ckpt["activation_mb"] < bf16["activation_mb"]


def test_policy_card_blocks_memory_cap_overage() -> None:
    card = build_precision_policy_card(
        MixedPrecisionRequest(precision="fp32", max_memory_mb=1),
        parameter_count=10_000_000,
        sequence_tokens=2048,
        hidden_dim=640,
        batch_size=1,
    )
    assert card["passed"] is False
    assert "exceeds cap" in card["errors"][-1]
