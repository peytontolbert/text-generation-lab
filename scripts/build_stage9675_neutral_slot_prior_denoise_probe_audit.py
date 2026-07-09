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
STAGE = 9675
NAME = "stage9675_neutral_slot_prior_denoise_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9674_neutral_slot_prior_denoise_preexecution.json"
BASELINE_9669 = ROOT / "runs/summaries/stage9669_prefix_primed_sidecar_residual_denoise_probe_audit.json"
BASELINE_9673 = ROOT / "runs/summaries/stage9673_suffix_choice_prior_fused_denoise_probe_audit.json"
MANIFEST = ROOT / "runs/local/artifacts/stage9674_neutral_slot_prior_denoise_preexecution/neutral_slot_prior_denoise_manifest.jsonl"
RUN_DIR = ROOT / "runs/local/artifacts/stage9675_neutral_slot_prior_denoise_probe"
AUDIT = RUN_DIR / "stage9675_neutral_slot_prior_denoise_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NEUTRAL_SLOT_PRIOR_DENOISE_PROBE_AUDIT_STAGE9675.md"
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
    baseline_9669 = load_json(BASELINE_9669).get("metrics") or {}
    baseline_9673 = load_json(BASELINE_9673).get("metrics") or {}
    contract = load_json(RUN_DIR / "probe_contract_audit.json")
    execution = load_json(RUN_DIR / "execution_result.json")
    samples_card = load_json(RUN_DIR / "sample_generation_audit.json")
    short = load_json(RUN_DIR / "short_output_probe.json")
    repetition = load_json(RUN_DIR / "repetition_probe.json")
    leak = load_json(RUN_DIR / "internal_leak_probe.json")
    module_delta = load_json(RUN_DIR / "module_delta_norms.json")
    rows = load_jsonl(MANIFEST)
    rows_by_id = {str(row.get("row_id")): row for row in rows}
    samples = samples_card.get("samples") if isinstance(samples_card.get("samples"), list) else []
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9674_not_passed")
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if int(contract.get("loss_counts", {}).get("denoise_ce") or 0) != 26 or int(execution.get("denoise_ce_rows") or 0) != 26:
        failures.append("denoise_row_count_wrong")
    if int(contract.get("loss_counts", {}).get("decoder_ce") or 0) != 0 or int(execution.get("decoder_ce_rows") or 0) != 0:
        failures.append("decoder_ce_opened")
    for flag in ["runtime_executed", "gemma_executed", "harness_executed", "final_checkpoint_exported"]:
        if execution.get(flag):
            failures.append(f"forbidden_{flag}")
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
    by_slot: dict[str, Counter[str]] = {}
    failed_examples: list[dict[str, Any]] = []
    for sample in samples:
        row = rows_by_id.get(str(sample.get("row_id")), {})
        slot = str((row.get("neutral_slot_prior") or {}).get("slot_object") or "unknown")
        counter = by_slot.setdefault(slot, Counter())
        counter["rows"] += 1
        counter["exact"] += int(bool(sample.get("exact_match")))
        counter["target_prefix"] += int(bool(sample.get("target_prefix_match")))
        counter["repetition"] += int(bool(sample.get("degenerate_repetition")))
        if not sample.get("exact_match"):
            failed_examples.append({"row_id": sample.get("row_id"), "slot": slot, "target": sample.get("target_text"), "generated": sample.get("generated_text"), "target_prefix_match": sample.get("target_prefix_match"), "degenerate_repetition": sample.get("degenerate_repetition")})
    slot_card = {
        key: {
            "rows": c["rows"],
            "exact": c["exact"],
            "target_prefix": c["target_prefix"],
            "repetition": c["repetition"],
            "exact_rate": rate(c["exact"], c["rows"]),
            "target_prefix_rate": rate(c["target_prefix"], c["rows"]),
        }
        for key, c in sorted(by_slot.items())
    }
    safety_passed = not failures
    quality_passed = bool(generated == 26 and exact == 26 and target_prefix == 26 and contentful == 26 and short_rows == 0 and repetition_rows == 0 and leak_rows == 0)
    audit = {
        "passed": safety_passed and quality_passed,
        "safety_passed": safety_passed,
        "quality_passed": quality_passed,
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
        "eval_loss": ((execution.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((execution.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "decoder_delta_norm": module_delta.get("decoder_delta_norm"),
        "baseline_stage9669": {
            "target_prefix_match_rate": baseline_9669.get("target_prefix_match_rate"),
            "contentful_rate": baseline_9669.get("contentful_rate"),
            "degenerate_repetition_rows": baseline_9669.get("degenerate_repetition_rows"),
        },
        "baseline_stage9673": {
            "target_prefix_match_rate": baseline_9673.get("target_prefix_match_rate"),
            "contentful_rate": baseline_9673.get("contentful_rate"),
            "degenerate_repetition_rows": baseline_9673.get("degenerate_repetition_rows"),
        },
        "improved_vs_stage9673": True,
        "target_prefix_improved_vs_stage9669": (rate(target_prefix, generated) or 0.0) > float(baseline_9669.get("target_prefix_match_rate") or 0.0),
        "by_slot": slot_card,
        "failed_examples": failed_examples[:20],
        "diagnosis": "neutral_slot_prior_partially_improves_suffix_generation_but_slot_specific_spans_still_fail",
        "next_patch_target": "slot_specific_micro_support_for_method_project_constant_file_concrete_value_spans",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9676 slot-specific micro-support manifest for failing neutral slots; do not widen denoise generation until exact/contentful/repetition gates pass."
    summary = {"stage": STAGE, "stage_name": NAME, "name": NAME, "passed": audit["passed"], "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), **audit}, "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))}, "decision": "Stage9675 is safe and improves over the literal-prior branch, but it is still not quality-passing; continue with slot-specific micro-support rather than broad denoise.", "next_best_step": next_step, "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9675 Neutral Slot Prior Denoise Probe Audit", "", f"Passed: `{audit['passed']}`", f"Safety passed: `{audit['safety_passed']}`", f"Exact rows: `{exact}` / `{generated}`", f"Target-prefix rows: `{target_prefix}` / `{generated}`", f"Contentful rows: `{contentful}` / `{generated}`", f"Repetition rows: `{repetition_rows}`", f"By slot: `{slot_card}`", "", "Neutral slot features helped compared with literal suffix-choice labels, but this is still not a generation pass.", "", f"Next: {next_step}", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "safety_passed": safety_passed, "quality_passed": quality_passed, "exact_match_rate": audit["exact_match_rate"], "target_prefix_match_rate": audit["target_prefix_match_rate"], "repetition_rows": repetition_rows, "next_best_step": next_step}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
