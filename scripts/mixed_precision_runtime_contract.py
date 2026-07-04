from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Precision = Literal["fp32", "bf16", "fp16"]


@dataclass(frozen=True)
class MixedPrecisionRequest:
    precision: Precision = "fp32"
    device: str = "cpu"
    use_autocast: bool = False
    use_grad_scaler: bool = False
    activation_checkpointing: bool = False
    max_memory_mb: int | None = None
    model_execution_authorized: bool = False
    training_authorized: bool = False


PRECISION_BYTES = {"fp32": 4.0, "bf16": 2.0, "fp16": 2.0}
ACTIVATION_CHECKPOINT_SAVING = 0.35
GRAD_SCALER_OVERHEAD_MB = 16


def request_from_dict(row: dict[str, Any]) -> MixedPrecisionRequest:
    precision = str(row.get("precision") or "fp32")
    if precision not in PRECISION_BYTES:
        raise ValueError(f"unsupported precision: {precision}")
    return MixedPrecisionRequest(
        precision=precision,  # type: ignore[arg-type]
        device=str(row.get("device") or "cpu"),
        use_autocast=bool(row.get("use_autocast", False)),
        use_grad_scaler=bool(row.get("use_grad_scaler", False)),
        activation_checkpointing=bool(row.get("activation_checkpointing", False)),
        max_memory_mb=(int(row["max_memory_mb"]) if row.get("max_memory_mb") is not None else None),
        model_execution_authorized=bool(row.get("model_execution_authorized", False)),
        training_authorized=bool(row.get("training_authorized", False)),
    )


def estimate_memory_mb(
    *,
    parameter_count: int,
    sequence_tokens: int,
    hidden_dim: int,
    batch_size: int,
    precision: Precision,
    optimizer_states: bool = False,
    activation_checkpointing: bool = False,
    use_grad_scaler: bool = False,
) -> dict[str, float]:
    bytes_per = PRECISION_BYTES[precision]
    param_mb = parameter_count * bytes_per / (1024 * 1024)
    grad_mb = parameter_count * bytes_per / (1024 * 1024) if optimizer_states else 0.0
    # AdamW moment states are normally fp32 even under mixed precision.
    optim_mb = parameter_count * 8.0 / (1024 * 1024) if optimizer_states else 0.0
    activation_mb = batch_size * sequence_tokens * hidden_dim * bytes_per / (1024 * 1024)
    if activation_checkpointing:
        activation_mb *= 1.0 - ACTIVATION_CHECKPOINT_SAVING
    scaler_mb = float(GRAD_SCALER_OVERHEAD_MB if use_grad_scaler else 0)
    total = param_mb + grad_mb + optim_mb + activation_mb + scaler_mb
    return {
        "parameter_mb": param_mb,
        "gradient_mb": grad_mb,
        "optimizer_state_mb": optim_mb,
        "activation_mb": activation_mb,
        "grad_scaler_mb": scaler_mb,
        "total_estimated_mb": total,
    }


def validate_mixed_precision_request(request: MixedPrecisionRequest) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if request.device == "cpu" and request.precision in {"fp16", "bf16"}:
        warnings.append("mixed precision on cpu is contract-only and should not be assumed performant")
    if request.precision == "fp32" and request.use_grad_scaler:
        errors.append("GradScaler is only valid for fp16 training")
    if request.precision == "bf16" and request.use_grad_scaler:
        errors.append("bf16 should not use GradScaler")
    if request.precision == "fp16" and request.training_authorized and not request.use_grad_scaler:
        errors.append("fp16 training requires GradScaler")
    if request.precision in {"fp16", "bf16"} and request.model_execution_authorized and not request.use_autocast:
        errors.append("mixed precision execution requires autocast")
    if request.use_autocast and request.precision == "fp32":
        errors.append("autocast should not be enabled for fp32 contract")
    if request.activation_checkpointing and not request.training_authorized:
        warnings.append("activation checkpointing is only meaningful for authorized training probes")
    return {
        "request": asdict(request),
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "authority": {
            "model_execution": request.model_execution_authorized,
            "training": request.training_authorized,
            "runtime": False,
            "source_body_emission": False,
        },
    }


def build_precision_policy_card(
    request: MixedPrecisionRequest,
    *,
    parameter_count: int,
    sequence_tokens: int,
    hidden_dim: int,
    batch_size: int,
) -> dict[str, Any]:
    validation = validate_mixed_precision_request(request)
    memory = estimate_memory_mb(
        parameter_count=parameter_count,
        sequence_tokens=sequence_tokens,
        hidden_dim=hidden_dim,
        batch_size=batch_size,
        precision=request.precision,
        optimizer_states=request.training_authorized,
        activation_checkpointing=request.activation_checkpointing,
        use_grad_scaler=request.use_grad_scaler,
    )
    errors = list(validation["errors"])
    if request.max_memory_mb is not None and memory["total_estimated_mb"] > request.max_memory_mb:
        errors.append(
            f"estimated memory {memory['total_estimated_mb']:.2f}MB exceeds cap {request.max_memory_mb}MB"
        )
    return {
        "passed": validation["passed"] and not errors,
        "request": validation["request"],
        "errors": errors,
        "warnings": validation["warnings"],
        "memory_estimate": memory,
        "precision_bytes": PRECISION_BYTES[request.precision],
        "requires_autocast": request.precision in {"fp16", "bf16"} and request.model_execution_authorized,
        "requires_grad_scaler": request.precision == "fp16" and request.training_authorized,
        "authority": validation["authority"],
    }


def safe_default_policy() -> dict[str, Any]:
    return build_precision_policy_card(
        MixedPrecisionRequest(precision="fp32", device="cpu"),
        parameter_count=102_654_362,
        sequence_tokens=2048,
        hidden_dim=640,
        batch_size=1,
    )
