#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9598
NAME = "stage9598_structured_head_architecture_contract"
SOURCE_SUMMARIES = [
    ROOT / "runs/summaries/stage9596_encoder_rope_order_sensitivity_audit.json",
    ROOT / "runs/summaries/stage9597_encoder_rope_minimal_sidecar_probe.json",
]
MODEL_FILE = ROOT / "legacy_src/agentkernel_lite/modeling_transformer.py"
TRAINING_LOOP = ROOT / "legacy_src/agentkernel_lite/training_loop.py"
RUN_ROOT = ROOT / "runs/local/artifacts" / NAME
AUDIT = RUN_ROOT / "structured_head_architecture_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_HEAD_ARCHITECTURE_CONTRACT_STAGE9598.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    RUN_ROOT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    source_cards = [load_json(path) for path in SOURCE_SUMMARIES]
    if any(card.get("passed") is not True for card in source_cards):
        failures.append("source_stage_not_passed")
    model_text = MODEL_FILE.read_text(encoding="utf-8")
    loop_text = TRAINING_LOOP.read_text(encoding="utf-8")
    encoder_rope_present = "self.self_attn = MultiHeadAttention(config, causal=False, use_rope=True)" in model_text
    encoder_rope_disabled_present = "self.self_attn = MultiHeadAttention(config, causal=False, use_rope=False)" in model_text
    structured_freeze_present = 'bucket.startswith("decoder") or bucket in {"lm_head", "embeddings"}' in loop_text
    optimizer_filter_present = "AdamW([parameter for parameter in model.parameters() if parameter.requires_grad]" in loop_text
    telemetry_present = '"structured_optimizer_isolated": True' in loop_text and '"structured_optimizer_frozen_bucket_prefixes": ["decoder", "lm_head", "embeddings"]' in loop_text
    if not encoder_rope_present or encoder_rope_disabled_present:
        failures.append("encoder_rope_contract_missing")
    if not structured_freeze_present:
        failures.append("structured_probe_freeze_contract_missing")
    if not optimizer_filter_present:
        failures.append("structured_probe_optimizer_filter_missing")
    if not telemetry_present:
        failures.append("structured_optimizer_telemetry_missing")

    stage9597 = source_cards[-1] if source_cards else {}
    stage9597_metrics = stage9597.get("metrics") if isinstance(stage9597.get("metrics"), dict) else {}
    if stage9597_metrics.get("eval_suffix_choice_exact") != 1.0 or stage9597_metrics.get("strict_suffix_choice_exact") != 1.0:
        failures.append("stage9597_quality_gate_not_locked")
    if stage9597_metrics.get("max_frozen_bucket_delta") != 0.0:
        failures.append("stage9597_frozen_bucket_delta_nonzero")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summaries": [str(path.relative_to(ROOT)) for path in SOURCE_SUMMARIES],
        "encoder_rope_present": encoder_rope_present,
        "encoder_rope_disabled_present": encoder_rope_disabled_present,
        "structured_probe_freeze_present": structured_freeze_present,
        "structured_probe_optimizer_filter_present": optimizer_filter_present,
        "structured_optimizer_telemetry_present": telemetry_present,
        "stage9597_eval_suffix_choice_exact": stage9597_metrics.get("eval_suffix_choice_exact"),
        "stage9597_strict_suffix_choice_exact": stage9597_metrics.get("strict_suffix_choice_exact"),
        "stage9597_max_frozen_bucket_delta": stage9597_metrics.get("max_frozen_bucket_delta"),
        "authority": dict(AUTHORITY_CLOSED),
        "runtime_executed": False,
        "decoder_ce_training_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Reconnect the learned suffix-choice controller to the residual-denoise route_0 duplicate repair path, keeping decoder CE/runtime/export closed."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Locked the structured-head architecture contract: encoder RoPE is required and structured-only probes must freeze decoder, LM-head, and shared embeddings.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9598 Structured Head Architecture Contract",
        "",
        f"Passed: `{audit['passed']}`",
        f"Encoder RoPE present: `{encoder_rope_present}`",
        f"Structured optimizer freeze present: `{structured_freeze_present}`",
        f"Optimizer filter present: `{optimizer_filter_present}`",
        f"Stage9597 eval/strict suffix exact: `{audit['stage9597_eval_suffix_choice_exact']}` / `{audit['stage9597_strict_suffix_choice_exact']}`",
        f"Stage9597 max frozen bucket delta: `{audit['stage9597_max_frozen_bucket_delta']}`",
        "",
        "Contract: structured heads must see ordered evidence, and structured-only probes must not mutate decoder/export buckets. Decoder, denoise, runtime, export, harness, and promotion remain closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
