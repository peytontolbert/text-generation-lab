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
STAGE = 9266
NAME = "stage9266_stage9265_stabilized_probe_diagnostic_audit"
RUN_DIR = ROOT / "runs/local/artifacts/stage9265_stabilized_target_100m_bounded_decoder_probe/bounded_decoder_probe"
SOURCE_REVIEW = ROOT / "runs/summaries/stage9264_stabilized_bounded_decoder_execution_review.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "stage9265_stabilized_probe_diagnostic_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STAGE9265_STABILIZED_PROBE_DIAGNOSTIC_AUDIT_STAGE9266.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_REVIEW)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution_payload = load_json(RUN_DIR / "execution_result.json")
    execution = execution_payload.get("execution_result", execution_payload)
    loss_steps = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    eval_losses = load_jsonl(RUN_DIR / "eval_loss_by_checkpoint.jsonl")
    generation = load_json(RUN_DIR / "sample_generation_audit.json")
    failures = load_json(RUN_DIR / "failure_bucket_card.json")
    leaks = load_json(RUN_DIR / "internal_leak_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    cleanup = load_json(RUN_DIR / "cleanup_proof.json")
    eos = load_json(RUN_DIR / "eos_length_audit.json")
    negative_rows = load_jsonl(RUN_DIR / "generated_repetition_negative_rows.jsonl")
    eval_by_split = {row.get("split"): row.get("loss") for row in eval_losses}
    first = float(loss_steps[0]["loss"]) if loss_steps else None
    last = float(loss_steps[-1]["loss"]) if loss_steps else None
    pre_clip_max = max(float(row.get("pre_clip_grad_norm", row.get("grad_norm", 0))) for row in loss_steps) if loss_steps else None
    post_clip_max = max(float(row.get("post_clip_grad_norm", 0)) for row in loss_steps) if loss_steps else None

    safety_passed = (
        source.get("passed") is True
        and contract.get("passed") is True
        and execution.get("final_checkpoint_exported") is False
        and execution.get("runtime_executed") is False
        and execution.get("gemma_executed") is False
        and execution.get("harness_executed") is False
        and execution.get("required_artifacts_written") is True
        and cleanup.get("cleanup_executed") is False
    )
    gate_passed = (
        safety_passed
        and generation.get("contentful_rate", 0) >= 0.50
        and generation.get("unterminated_rate", 1) <= 0.25
        and repetition.get("degenerate_repetition_rate", 1) <= 0.10
        and generation.get("target_prefix_match_rate", 0) >= 0.10
        and leaks.get("generated_internal_token_rows", 1) == 0
        and short.get("short_or_junk_rate", 1) == 0
        and post_clip_max is not None
        and post_clip_max <= 10.0
    )
    return {
        "passed": safety_passed,
        "quality_gate_passed": gate_passed,
        "failures": [] if gate_passed else ["stabilized_decoder_quality_gate_failed"],
        "metrics": {
            "execution_safety_passed": safety_passed,
            "quality_gate_passed": gate_passed,
            "train_loss_first": first,
            "train_loss_last": last,
            "train_loss_drop": (first - last) if first is not None and last is not None else None,
            "eval_loss": eval_by_split.get("eval"),
            "strict_eval_loss": eval_by_split.get("strict_eval"),
            "eos_loss_weight": eos.get("eos_loss_weight"),
            "contentful_generation_rate": generation.get("contentful_rate"),
            "unterminated_generation_rate": generation.get("unterminated_rate"),
            "target_prefix_match_rate": generation.get("target_prefix_match_rate"),
            "degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
            "short_or_junk_rate": short.get("short_or_junk_rate"),
            "generated_internal_token_rows": leaks.get("generated_internal_token_rows"),
            "failure_buckets": failures.get("buckets", {}),
            "pre_clip_grad_norm_max": pre_clip_max,
            "post_clip_grad_norm_max": post_clip_max,
            "repetition_negative_rows": sum(1 for row in negative_rows if row.get("negative_row")),
            "estimated_parameter_count": (execution.get("implementation") or {}).get("estimated_parameter_count"),
        },
        "authority": dict(AUTHORITY_CLOSED),
        "diagnosis": {
            "primary_failure": "eos_weighting_reduced_unterminated_outputs_only_marginally_and_hurt_eval_loss",
            "next_patch": "Convert generated repetition failures into denoise/repair rows and add teacher-forced EOS calibration before another target-100M decoder CE run.",
        },
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
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Stage9265 executed safely but failed decoder quality gates. EOS weighting gave only marginal generation improvement and worsened eval loss.",
        "next_best_step": "Build Stage9267 repetition-to-denoise repair manifest from Stage9265 generated failures plus EOS calibration rows; do not run another target-100M decoder CE probe yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("# Stage9266 Stage9265 Stabilized Probe Diagnostic Audit\n\nStage9265 was execution-safe but failed quality gates. Next step is a repetition-to-denoise repair manifest and EOS calibration rows before another target-100M decoder CE run.\n", encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "quality_gate_passed": audit["quality_gate_passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
