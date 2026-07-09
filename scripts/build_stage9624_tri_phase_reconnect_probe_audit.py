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
STAGE = 9624
NAME = "stage9624_tri_phase_reconnect_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9623_tri_phase_reconnect_tiny_probe.json"
PREV_SUMMARY = ROOT / "runs/summaries/stage9619_integrated_residual_phrase_tiny_probe.json"
PHASE3_DIR = ROOT / "runs/local/artifacts/stage9623_tri_phase_reconnect_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "tri_phase_reconnect_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRI_PHASE_RECONNECT_PROBE_AUDIT_STAGE9624.md"
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


def classify_failures(samples: list[dict[str, Any]]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for sample in samples:
        if sample.get("exact_match") and sample.get("target_prefix_match"):
            continue
        target = str(sample.get("target_text") or "").lower()
        generated = str(sample.get("generated_text") or "").lower()
        if "localized repair step" in target:
            bucket = "localized_repair_step"
        elif "relevant repair region" in target:
            bucket = "relevant_repair_region"
        elif "checked verifier condition" in target:
            bucket = "checked_verifier_condition"
        elif "wrapper plan" in target:
            bucket = "wrapper_plan"
        else:
            bucket = "other"
        if "rep rep" in generated:
            bucket += ":rep_token_loop"
        elif "keepside" in generated:
            bucket += ":keepside_loop"
        elif "repair repair" in generated:
            bucket += ":repair_loop"
        elif "rep verified" in generated:
            bucket += ":verified_substitution"
        counts[bucket] += 1
        rows.append(
            {
                "row_id": sample.get("row_id"),
                "split": sample.get("split"),
                "bucket": bucket,
                "prefix": sample.get("generation_prefix_text"),
                "generated": str(sample.get("generated_text") or "")[:220],
                "target": str(sample.get("target_text") or "")[:220],
                "target_prefix_match": sample.get("target_prefix_match"),
                "degenerate_repetition": sample.get("degenerate_repetition"),
                "stopped_on_eos": sample.get("stopped_on_eos"),
            }
        )
    return dict(counts), rows[:12]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    previous = load_json(PREV_SUMMARY)
    generation = load_json(PHASE3_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE3_DIR / "repetition_probe.json")
    leak = load_json(PHASE3_DIR / "internal_leak_probe.json")
    short = load_json(PHASE3_DIR / "short_output_probe.json")
    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []
    bucket_counts, failure_rows = classify_failures(samples)

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9623_safety_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9623_quality_failure_not_recorded")
    if source.get("metrics", {}).get("model_reused_in_memory_between_phases") is not True:
        failures.append("in_memory_reuse_not_recorded")
    if source.get("metrics", {}).get("decoder_ce_rows") != 0:
        failures.append("decoder_ce_rows_present")

    prev_metrics = previous.get("metrics") if isinstance(previous.get("metrics"), dict) else {}
    current_metrics = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "previous_summary": str(PREV_SUMMARY.relative_to(ROOT)),
        "stage9619_contentful_rate": prev_metrics.get("phase2_contentful_generation_rate"),
        "stage9619_target_prefix_match_rate": prev_metrics.get("phase2_target_prefix_match_rate"),
        "stage9623_contentful_rate": current_metrics.get("phase3_contentful_generation_rate"),
        "stage9623_target_prefix_match_rate": current_metrics.get("phase3_target_prefix_match_rate"),
        "stage9623_prefix_start_rate": current_metrics.get("phase3_generation_prefix_start_rate"),
        "stage9623_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "stage9623_unterminated_rate": repetition.get("unterminated_rate"),
        "stage9623_short_or_junk_rows": short.get("short_or_junk_rows"),
        "stage9623_internal_leak_rows": leak.get("generated_internal_token_rows"),
        "model_reused_in_memory_between_phases": current_metrics.get("model_reused_in_memory_between_phases"),
        "decoder_ce_rows": current_metrics.get("decoder_ce_rows"),
        "runtime_executed": current_metrics.get("runtime_executed"),
        "failure_bucket_counts": bucket_counts,
        "sample_failure_rows": failure_rows,
        "decision": "Tri-phase in-memory reconnect is a real improvement over the one-pass mixed objective, but it still fails quality on a small set of phrase-level continuation buckets. Patch targeted hard phrase support rows before widening.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9625 targeted hard phrase continuation manifest for localized_repair_step, relevant_repair_region, and checked_verifier_condition buckets; then contract-audit before another tiny tri-phase probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9624 Tri-Phase Reconnect Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Stage9619 contentful / prefix: `{audit['stage9619_contentful_rate']}` / `{audit['stage9619_target_prefix_match_rate']}`",
        f"Stage9623 contentful / prefix: `{audit['stage9623_contentful_rate']}` / `{audit['stage9623_target_prefix_match_rate']}`",
        f"Stage9623 repetition rate: `{audit['stage9623_repetition_rate']}`",
        f"Failure buckets: `{audit['failure_bucket_counts']}`",
        "",
        "Tri-phase handoff is now real and safe, but the residual decoder still confuses a few phrase continuations. The next patch should add targeted hard phrase rows rather than broad training.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
