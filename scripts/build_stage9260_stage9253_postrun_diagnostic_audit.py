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
STAGE = 9260
NAME = "stage9260_stage9253_postrun_diagnostic_audit"
RUN_DIR = ROOT / "runs/local/artifacts/stage9253_semantic_target_repair_target_100m_bounded_tiny_probe/bounded_decoder_probe"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9251_semantic_target_repair_target_100m_contract_only_preflight.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "stage9253_postrun_diagnostic_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STAGE9253_POSTRUN_DIAGNOSTIC_AUDIT_STAGE9260.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

REQUIRED_ARTIFACTS = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_token_loss.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "internal_token_logit_summary.json",
    "row_dynamics_history.jsonl",
    "eos_length_audit.json",
    "short_output_probe.json",
    "repetition_probe.json",
    "internal_leak_probe.json",
    "sample_generation_audit.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def artifact_card() -> dict[str, Any]:
    details = {}
    missing = []
    empty = []
    for name in REQUIRED_ARTIFACTS:
        path = RUN_DIR / name
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        details[name] = {"exists": exists, "size_bytes": size}
        if not exists:
            missing.append(name)
        elif size <= 0:
            empty.append(name)
    checkpoint_like = []
    if RUN_DIR.exists():
        for path in RUN_DIR.rglob("*"):
            if path.is_file() and path.name.endswith((".pt", ".bin", ".safetensors", ".ckpt")):
                checkpoint_like.append(str(path.relative_to(ROOT)))
    return {
        "required_artifacts": len(REQUIRED_ARTIFACTS),
        "missing_artifacts": missing,
        "empty_artifacts": empty,
        "checkpoint_like_artifacts": checkpoint_like,
        "details": details,
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
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
    deltas = load_json(RUN_DIR / "module_delta_norms.json")
    artifacts = artifact_card()

    train_first = float(loss_steps[0]["loss"]) if loss_steps else None
    train_last = float(loss_steps[-1]["loss"]) if loss_steps else None
    train_loss_drop = (train_first - train_last) if train_first is not None and train_last is not None else None
    train_loss_drop_rate = (train_loss_drop / train_first) if train_loss_drop is not None and train_first else None
    eval_by_split = {row.get("split"): row.get("loss") for row in eval_losses}

    safety_passed = (
        source.get("passed") is True
        and contract.get("passed") is True
        and execution.get("final_checkpoint_exported") is False
        and execution.get("runtime_executed") is False
        and execution.get("gemma_executed") is False
        and execution.get("harness_executed") is False
        and not artifacts["missing_artifacts"]
        and not artifacts["empty_artifacts"]
        and not artifacts["checkpoint_like_artifacts"]
    )
    decoder_quality_passed = (
        generation.get("generated_rows") == 16
        and generation.get("contentful_rate", 0) >= 0.8
        and generation.get("unterminated_rows", 1) == 0
        and generation.get("target_prefix_match_rate", 0) > 0.25
        and leaks.get("generated_internal_token_rows", 1) == 0
        and repetition.get("degenerate_repetition_rate", 1) <= 0.05
        and short.get("short_or_junk_rate", 1) == 0
    )
    failures_list: list[str] = []
    if not safety_passed:
        failures_list.append("execution_safety_or_artifact_contract_failed")
    if not decoder_quality_passed:
        failures_list.append("decoder_quality_gate_failed")
    if train_loss_drop_rate is None or train_loss_drop_rate <= 0:
        failures_list.append("train_loss_did_not_decrease")
    if loss_steps and float(loss_steps[0].get("grad_norm", 0)) > 1e8:
        failures_list.append("initial_gradient_explosion_observed")

    return {
        "passed": safety_passed,
        "probe_quality_passed": decoder_quality_passed,
        "failures": failures_list,
        "metrics": {
            "execution_safety_passed": safety_passed,
            "decoder_quality_passed": decoder_quality_passed,
            "train_loss_first": train_first,
            "train_loss_last": train_last,
            "train_loss_drop": train_loss_drop,
            "train_loss_drop_rate": train_loss_drop_rate,
            "eval_loss": eval_by_split.get("eval"),
            "strict_eval_loss": eval_by_split.get("strict_eval"),
            "generated_rows": generation.get("generated_rows"),
            "contentful_generation_rate": generation.get("contentful_rate"),
            "unterminated_generation_rate": generation.get("unterminated_rate"),
            "target_prefix_match_rate": generation.get("target_prefix_match_rate"),
            "generated_internal_token_rows": leaks.get("generated_internal_token_rows"),
            "short_or_junk_rate": short.get("short_or_junk_rate"),
            "degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
            "failure_buckets": failures.get("buckets", {}),
            "decoder_delta_norm": deltas.get("decoder_delta_norm"),
            "encoder_delta_norm": deltas.get("encoder_delta_norm"),
            "structured_head_delta_norm": deltas.get("structured_head_delta_norm"),
            "cleanup_executed": cleanup.get("cleanup_executed"),
            "checkpoint_like_artifacts": len(artifacts["checkpoint_like_artifacts"]),
            "missing_artifacts": len(artifacts["missing_artifacts"]),
            "empty_artifacts": len(artifacts["empty_artifacts"]),
            "estimated_parameter_count": (execution.get("implementation") or {}).get("estimated_parameter_count"),
        },
        "artifacts": artifacts,
        "authority": dict(AUTHORITY_CLOSED),
        "diagnosis": {
            "primary_failure": "unterminated_repetitive_generation_after_ce_loss_drop",
            "interpretation": "The 100M target path executes and learns CE signal, but the decoder still lacks EOS/continuation control and produces repeated non-target text.",
            "next_patch": "Build a bounded decoder stabilization package with EOS-positive/negative weighting, generated-repetition negatives, and a lower-LR/warmer micro-overfit rerun before scaling rows.",
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
        "passed": bool(audit["passed"]),
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Stage9253 execution was safe and artifact-complete, but decoder quality failed: generation is unterminated/repetitive with zero contentful outputs.",
        "next_best_step": "Build Stage9261 bounded decoder stabilization design: EOS/continuation loss, repetition negatives, initial-gradient control, and one capped rerun ticket.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9260 Stage9253 Post-Run Diagnostic Audit",
                "",
                "Stage9253 executed the authorized target-100M bounded decoder CE probe.",
                "",
                f"Execution safety passed: {audit['metrics']['execution_safety_passed']}",
                f"Decoder quality passed: {audit['metrics']['decoder_quality_passed']}",
                f"Train loss: {audit['metrics']['train_loss_first']} -> {audit['metrics']['train_loss_last']}",
                f"Eval / strict loss: {audit['metrics']['eval_loss']} / {audit['metrics']['strict_eval_loss']}",
                f"Contentful generation rate: {audit['metrics']['contentful_generation_rate']}",
                f"Unterminated generation rate: {audit['metrics']['unterminated_generation_rate']}",
                f"Degenerate repetition rate: {audit['metrics']['degenerate_repetition_rate']}",
                "",
                "Conclusion: the target 100M transformer path is executable and receives CE gradients, but the decoder generation gate still fails. Do not scale rows yet.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "probe_quality_passed": audit["probe_quality_passed"], "metrics": summary["metrics"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
