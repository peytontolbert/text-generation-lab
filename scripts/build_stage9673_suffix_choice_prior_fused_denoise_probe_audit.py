#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9673
NAME = "stage9673_suffix_choice_prior_fused_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9672_suffix_choice_prior_fused_denoise_preexecution.json"
BASELINE_SUMMARY = ROOT / "runs/summaries/stage9669_prefix_primed_sidecar_residual_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9672_suffix_choice_prior_fused_denoise_preexecution/suffix_choice_prior_fused_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9673_suffix_choice_prior_fused_denoise_probe"
AUDIT = RUN_DIR / "stage9673_suffix_choice_prior_fused_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_PRIOR_FUSED_DENOISE_PROBE_AUDIT_STAGE9673.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def rate(n: int, d: int) -> float | None:
    return n / d if d else None


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    source = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE_SUMMARY)
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    rows = load_jsonl(MANIFEST)
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    missing = [
        name
        for name in [
            "probe_contract_audit.json",
            "execution_result.json",
            "sample_generation_audit.json",
            "row_token_loss.jsonl",
            "row_gradient_norms.jsonl",
            "row_dynamics_history.jsonl",
            "activation_summary.jsonl",
            "module_delta_norms.json",
            "cleanup_proof.json",
            "short_output_probe.json",
            "repetition_probe.json",
            "internal_leak_probe.json",
            "denoise_repair_quality_audit.json",
        ]
        if not (RUN_DIR / name).exists()
    ]
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9672_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 26 or int(execution.get("denoise_ce_rows") or 0) != 26:
        failures.append("denoise_row_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(execution.get("decoder_ce_rows") or 0) != 0:
        failures.append("decoder_ce_opened")
    for flag in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if execution.get(flag):
            failures.append(f"forbidden_{flag}")
    if missing:
        failures.append("required_artifacts_missing")
    generated = int(samples_card.get("generated_rows") or execution.get("generated_rows") or 0)
    exact = int(samples_card.get("exact_match_rows") or 0)
    target_prefix = int(samples_card.get("target_prefix_match_rows") or round(float(execution.get("target_prefix_match_rate") or 0.0) * generated))
    prefix_start = int(samples_card.get("generation_prefix_start_rows") or round(float(execution.get("generation_prefix_start_rate") or 0.0) * generated))
    contentful = int(samples_card.get("contentful_rows") or round(float(execution.get("contentful_generation_rate") or 0.0) * generated))
    short_rows = int(short.get("short_or_junk_rows") or 0)
    repetition_rows = int(repetition.get("generated_repetition_rows") or 0)
    leak_rows = int(leak.get("generated_internal_token_rows") or 0)
    prior_counts = Counter(str(row.get("suffix_choice_prior_source")) for row in rows)
    repeated_samples = [
        {
            "row_id": sample.get("row_id"),
            "target": sample.get("target_text"),
            "generated": sample.get("generated_text"),
        }
        for sample in samples
        if sample.get("degenerate_repetition")
    ][:12]
    safety_passed = not failures
    baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    audit = {
        "passed": False,
        "safety_passed": safety_passed,
        "quality_passed": False,
        "failures": failures,
        "missing_artifacts": missing,
        "manifest_rows": len(rows),
        "generated_rows": generated,
        "exact_match_rows": exact,
        "exact_match_rate": rate(exact, generated),
        "target_prefix_match_rows": target_prefix,
        "target_prefix_match_rate": rate(target_prefix, generated),
        "generation_prefix_start_rows": prefix_start,
        "generation_prefix_start_rate": rate(prefix_start, generated),
        "contentful_rows": contentful,
        "contentful_rate": rate(contentful, generated),
        "short_or_junk_rows": short_rows,
        "degenerate_repetition_rows": repetition_rows,
        "generated_internal_token_rows": leak_rows,
        "train_rows": execution.get("train_rows"),
        "eval_rows": execution.get("eval_rows"),
        "strict_rows": execution.get("strict_rows"),
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
        "prior_source_counts": dict(sorted(prior_counts.items())),
        "baseline_stage9669": {
            "target_prefix_match_rate": baseline_metrics.get("target_prefix_match_rate"),
            "contentful_rate": baseline_metrics.get("contentful_rate"),
            "degenerate_repetition_rows": baseline_metrics.get("degenerate_repetition_rows"),
        },
        "regressed_vs_stage9669": True,
        "repeated_samples": repeated_samples,
        "diagnosis": "literal_suffix_choice_prior_labels_destabilized_generation_and_reintroduced_repetition",
        "next_patch_target": "neutral_slot_feature_prior_or_controller_gated_render_without_symbolic_label_text",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Reject literal suffix-choice-prior generation branch; build Stage9674 neutral slot-feature prior manifest or keep suffix_choice as controller-only telemetry before generation."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": False,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Stage9673 remained safe but regressed generation quality; do not continue with literal suffix-choice prior labels in model input.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9673 Suffix Choice Prior Fused Denoise Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Safety passed: `{audit['safety_passed']}`",
                f"Exact rows: `{exact}` / `{generated}`",
                f"Target-prefix rows: `{target_prefix}` / `{generated}`",
                f"Generation-prefix-start rows: `{prefix_start}` / `{generated}`",
                f"Contentful rows: `{contentful}` / `{generated}`",
                f"Repetition rows: `{repetition_rows}`",
                f"Internal leak rows: `{leak_rows}`",
                "",
                "The suffix-choice sidecar is learnable, but injecting literal suffix-choice labels into denoise generation made output worse than Stage9669 and reintroduced repetition.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": False, "safety_passed": safety_passed, "target_prefix_match_rate": audit["target_prefix_match_rate"], "contentful_rate": audit["contentful_rate"], "repetition_rows": repetition_rows, "next_best_step": next_step}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
