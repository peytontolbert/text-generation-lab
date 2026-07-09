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
STAGE = 9604
NAME = "stage9604_two_phase_denoise_generation_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9603_two_phase_suffix_denoise_tiny_probe.json"
PHASE2_DIR = ROOT / "runs/local/artifacts/stage9603_two_phase_suffix_denoise_tiny_probe/two_phase_probe/phase2_residual_denoise_probe"
SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "two_phase_denoise_generation_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TWO_PHASE_DENOISE_GENERATION_FAILURE_AUDIT_STAGE9604.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    quality = load_json(PHASE2_DIR / "denoise_repair_quality_audit.json")
    generation = load_json(PHASE2_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE2_DIR / "repetition_probe.json")
    leak = load_json(PHASE2_DIR / "internal_leak_probe.json")
    short = load_json(PHASE2_DIR / "short_output_probe.json")
    rows = load_jsonl(SOURCE_MANIFEST)

    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []
    generated_texts = [str(sample.get("generated_text", "")) for sample in samples]
    target_texts = [str(sample.get("target_text", "")) for sample in samples]
    generated_prefixes = Counter(text.split("::", 1)[0].strip() for text in generated_texts if text)
    target_prefixes = Counter(text.split("::", 1)[0].strip() for text in target_texts if text)
    repeated_bound_rows = [
        str(sample.get("row_id"))
        for sample in samples
        if "BOUND_BOUND" in str(sample.get("generated_text", ""))
    ]
    manifest_target_prefixes = Counter(
        str((row.get("target") or {}).get("repair_bucket", "missing")) for row in rows
    )
    manifest_failure_types = Counter(
        str((row.get("target") or {}).get("failure_type", "missing")) for row in rows
    )
    model_input_key_counts = Counter()
    for row in rows:
        for key in (row.get("model_input") or {}):
            model_input_key_counts[key] += 1

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9603_safety_probe_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9603_quality_gate_not_failed_as_expected")
    if quality.get("contentful_generation_rate") != 0.0:
        failures.append("unexpected_contentful_generation_rate")
    if generation.get("generation_prefix_field") is not None:
        failures.append("generation_prefix_field_unexpectedly_present")
    if repetition.get("degenerate_repetition_rate") != 1.0:
        failures.append("unexpected_repetition_rate")
    if leak.get("generated_internal_token_rows") not in {0, None}:
        failures.append("internal_token_leak_present")
    if short.get("short_or_junk_rows") not in {0, None}:
        failures.append("short_or_junk_rows_present")

    root_cause = {
        "phase1_suffix_choice_solved": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact") == 1.0
        and source.get("metrics", {}).get("phase1_strict_suffix_choice_exact") == 1.0,
        "phase2_target_rendering_is_symbolic_label_surface": True,
        "generation_prefix_field_missing": generation.get("generation_prefix_field") is None,
        "generated_repeats_bound_token": len(repeated_bound_rows) == generation.get("generated_rows"),
        "target_surface_is_repair_bucket_plus_failure_type": True,
    }
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "source_manifest": str(SOURCE_MANIFEST.relative_to(ROOT)),
        "stage9603_quality_gate": source.get("metrics", {}).get("quality_gate"),
        "phase1_eval_suffix_choice_exact": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact"),
        "phase1_strict_suffix_choice_exact": source.get("metrics", {}).get("phase1_strict_suffix_choice_exact"),
        "phase2_generated_rows": generation.get("generated_rows"),
        "phase2_contentful_generation_rate": quality.get("contentful_generation_rate"),
        "phase2_target_prefix_match_rate": quality.get("target_prefix_match_rate"),
        "phase2_generation_prefix_field": generation.get("generation_prefix_field"),
        "phase2_generation_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "phase2_degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "phase2_unterminated_rate": repetition.get("unterminated_rate"),
        "phase2_internal_leak_rows": leak.get("generated_internal_token_rows"),
        "phase2_short_or_junk_rows": short.get("short_or_junk_rows"),
        "generated_prefixes": dict(generated_prefixes),
        "target_prefixes_in_samples": dict(target_prefixes),
        "repeated_bound_rows": repeated_bound_rows,
        "manifest_rows": len(rows),
        "manifest_target_prefixes": dict(manifest_target_prefixes),
        "manifest_failure_types": dict(manifest_failure_types),
        "model_input_has_literal_prefix_redacted": model_input_key_counts.get("literal_prefix_redacted", 0) == len(rows),
        "model_input_has_generation_prefix": any("generation_prefix" in key for key in model_input_key_counts),
        "root_cause": root_cause,
        "decision": "Do not rerun broad denoise training. Patch the residual denoise target/prefix surface so the decoder learns a bounded natural repair span instead of repeating the symbolic BOUND token.",
        "recommended_patch": {
            "stage9605": "build_prefix_primed_residual_denoise_manifest_or_renderer_patch",
            "requirements": [
                "keep decoder_ce closed",
                "keep runtime/Gemma/harness/export closed",
                "keep suffix_choice sidecar as phase1 gate",
                "add an audited generation_prefix_field or bounded active_prefix span",
                "avoid copying full target text into model input",
                "make BOUND a structural boundary marker, not the dominant free token in generation",
                "rerun contract preflight before any execution",
            ],
            "future_pass_gate": {
                "phase1_eval_suffix_choice_exact": 1.0,
                "phase1_strict_suffix_choice_exact": 1.0,
                "phase2_contentful_generation_rate": 1.0,
                "phase2_degenerate_repetition_rate": 0.0,
                "phase2_unterminated_rate": 0.0,
                "phase2_internal_leak_rows": 0,
                "phase2_target_prefix_match_rate_min": 0.95,
            },
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = "Build Stage9605 as a prefix-primed residual-denoise manifest/renderer patch, then run a contract-only preflight before another tiny execution."
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
    DOC.write_text(
        "\n".join(
            [
                "# Stage9604 Two-Phase Denoise Generation Failure Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Stage9603 quality gate: `{audit['stage9603_quality_gate']}`",
                f"Phase1 eval/strict suffix exact: `{audit['phase1_eval_suffix_choice_exact']}` / `{audit['phase1_strict_suffix_choice_exact']}`",
                f"Phase2 contentful rate: `{audit['phase2_contentful_generation_rate']}`",
                f"Phase2 repetition rate: `{audit['phase2_degenerate_repetition_rate']}`",
                f"Phase2 unterminated rate: `{audit['phase2_unterminated_rate']}`",
                f"Generation prefix field: `{audit['phase2_generation_prefix_field']}`",
                "",
                "Finding: phase 1 solved the structured suffix-choice gate, but phase 2 generated repeated `BOUND` tokens on every sampled row. The source target surface is symbolic (`repair_bucket :: failure_type`) and no generation prefix field is active.",
                "",
                "Decision: do not rerun broad denoise training. Patch the residual denoise rendering/prefix surface first, keeping decoder CE, runtime, Gemma, harness, checkpoint export, and promotion closed.",
                "",
                f"Next: {next_step}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
