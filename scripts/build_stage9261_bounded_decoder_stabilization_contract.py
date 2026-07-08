#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9261
NAME = "stage9261_bounded_decoder_stabilization_contract"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9260_stage9253_postrun_diagnostic_audit/stage9253_postrun_diagnostic_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "bounded_decoder_stabilization_contract.json"
AUDIT = OUT_DIR / "bounded_decoder_stabilization_contract_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_STABILIZATION_CONTRACT_STAGE9261.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_TRAINER_PATCHES = [
    {
        "patch_id": "eos_weighted_token_loss",
        "required_flag": "--eos-loss-weight",
        "default_for_next_probe": 4.0,
        "reason": "Stage9253 generated 16/16 unterminated rows; EOS token positions need explicit weighted CE telemetry.",
    },
    {
        "patch_id": "post_clip_gradient_telemetry",
        "required_field": "post_clip_grad_norm",
        "threshold_for_next_probe": 10.0,
        "reason": "Stage9253 first pre-clip grad norm was 3.4698182656e11, so the next probe must distinguish clipped stability from raw explosion.",
    },
    {
        "patch_id": "repetition_negative_replay",
        "required_artifact": "generated_repetition_negative_rows.jsonl",
        "reason": "Stage9253 had 7/16 degenerate repetition rows; generated failures should become explicit negative/stabilization examples.",
    },
    {
        "patch_id": "eos_length_bucket_audit",
        "required_artifact": "eos_length_bucket_audit.json",
        "reason": "The next probe must report EOS hit rate and target length by language/surface, not only aggregate generation rows.",
    },
    {
        "patch_id": "lower_lr_rerun_ticket",
        "required_limit": {"learning_rate": 1e-5, "max_steps": 16, "max_train_rows": 32},
        "reason": "The next target-100M rerun should test stabilization, not scale exposure.",
    },
]

QUALITY_GATES = {
    "execution_safety_passed": True,
    "generated_internal_token_rows": 0,
    "short_or_junk_rate_max": 0.0,
    "unterminated_generation_rate_max": 0.25,
    "degenerate_repetition_rate_max": 0.10,
    "contentful_generation_rate_min": 0.50,
    "target_prefix_match_rate_min": 0.10,
    "post_clip_grad_norm_max": 10.0,
    "checkpoint_like_artifacts": 0,
}

NEXT_PROBE_LIMITS = {
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 16,
    "batch_size": 2,
    "learning_rate": 1e-5,
    "decoder_ce_weight": 1.0,
    "eos_loss_weight": 4.0,
    "structured_aux_weight": 0.0,
    "denoise_weight": 0.0,
    "max_generation_rows": 16,
    "max_generation_tokens": 96,
    "checkpoint_export": False,
    "runtime": False,
    "gemma": False,
    "harness": False,
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract(source: dict[str, Any]) -> dict[str, Any]:
    metrics = source.get("metrics") or {}
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "source_stage": 9260,
        "contract_status": "DESIGN_ONLY_NO_EXECUTION",
        "observed_failure": {
            "train_loss_drop_rate": metrics.get("train_loss_drop_rate"),
            "eval_loss": metrics.get("eval_loss"),
            "strict_eval_loss": metrics.get("strict_eval_loss"),
            "contentful_generation_rate": metrics.get("contentful_generation_rate"),
            "unterminated_generation_rate": metrics.get("unterminated_generation_rate"),
            "degenerate_repetition_rate": metrics.get("degenerate_repetition_rate"),
            "target_prefix_match_rate": metrics.get("target_prefix_match_rate"),
            "generated_internal_token_rows": metrics.get("generated_internal_token_rows"),
            "initial_gradient_explosion_observed": True,
        },
        "required_trainer_patches": REQUIRED_TRAINER_PATCHES,
        "quality_gates_for_next_probe": QUALITY_GATES,
        "next_probe_limits": NEXT_PROBE_LIMITS,
        "blocked_until_patched": [
            "second_target_100m_bounded_decoder_execution",
            "decoder_ce_row_scaleup",
            "bounded_decoder_success_claim",
            "gemma_comparison",
            "harness_or_product_scoring",
            "checkpoint_promotion",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }


def audit_contract(contract: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    metrics = source.get("metrics") or {}
    if source.get("passed") is not True:
        failures.append("source_stage9260_audit_not_passed")
    if metrics.get("execution_safety_passed") is not True:
        failures.append("source_execution_safety_not_passed")
    if metrics.get("decoder_quality_passed") is not False:
        failures.append("source_decoder_quality_not_recorded_as_failure")
    if contract.get("contract_status") != "DESIGN_ONLY_NO_EXECUTION":
        failures.append("wrong_contract_status")
    if any((contract.get("authority") or {}).values()):
        failures.append("authority_open")
    patch_ids = {patch.get("patch_id") for patch in contract.get("required_trainer_patches") or []}
    for required in ["eos_weighted_token_loss", "post_clip_gradient_telemetry", "repetition_negative_replay", "eos_length_bucket_audit", "lower_lr_rerun_ticket"]:
        if required not in patch_ids:
            failures.append(f"missing_patch:{required}")
    limits = contract.get("next_probe_limits") or {}
    if limits.get("learning_rate") != 1e-5:
        failures.append("next_probe_lr_not_lowered")
    if limits.get("checkpoint_export") is not False or limits.get("runtime") is not False or limits.get("gemma") is not False or limits.get("harness") is not False:
        failures.append("next_probe_forbidden_authority_open")
    gates = contract.get("quality_gates_for_next_probe") or {}
    if gates.get("unterminated_generation_rate_max", 1) > 0.25:
        failures.append("unterminated_gate_too_weak")
    if gates.get("degenerate_repetition_rate_max", 1) > 0.10:
        failures.append("repetition_gate_too_weak")
    serialized = json.dumps(contract, sort_keys=True).lower()
    for token in ["source_text", "target_text", "hidden_eval", "locked_eval", "checkpoint_export\": true"]:
        if token in serialized:
            failures.append(f"forbidden_token:{token}")
    return {
        "passed": not failures,
        "failures": failures,
        "required_trainer_patches": len(contract.get("required_trainer_patches") or []),
        "quality_gates": len(contract.get("quality_gates_for_next_probe") or {}),
        "next_probe_learning_rate": limits.get("learning_rate"),
        "authority": dict(AUTHORITY_CLOSED),
    }


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_AUDIT)
    contract = build_contract(source)
    audit = audit_contract(contract, source)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Defined the bounded decoder stabilization contract after Stage9253: EOS weighting, repetition negatives, post-clip gradient telemetry, and lower-LR rerun are required before another target-100M decoder probe.",
        "next_best_step": "Patch trainer command/runtime for --eos-loss-weight, post_clip_grad_norm telemetry, and repetition-negative artifact generation; then run contract-only preflight before any second execution.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9261 Bounded Decoder Stabilization Contract",
                "",
                "Stage9253 proved the recovered target-100M transformer path executes and receives decoder CE gradients, but generation failed.",
                "",
                "Required next changes:",
                "",
                "- Add `--eos-loss-weight` and EOS-position token-loss telemetry.",
                "- Record post-clip gradient norm separately from raw pre-clip norm.",
                "- Materialize generated repetition failures as negative/stabilization rows.",
                "- Add EOS/length bucket audit by language and surface.",
                "- Rerun at lower LR (`1e-5`) with the same tiny row caps before any scale-up.",
                "",
                "Blocked until those patches exist: second target-100M bounded decoder execution, row scale-up, Gemma comparison, harness scoring, and checkpoint promotion.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
