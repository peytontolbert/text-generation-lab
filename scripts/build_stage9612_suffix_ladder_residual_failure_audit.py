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
STAGE = 9612
NAME = "stage9612_suffix_ladder_residual_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9611_suffix_ladder_two_phase_tiny_probe.json"
PHASE2_DIR = ROOT / "runs/local/artifacts/stage9611_suffix_ladder_two_phase_tiny_probe/two_phase_probe/phase2_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "suffix_ladder_residual_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_LADDER_RESIDUAL_FAILURE_AUDIT_STAGE9612.md"
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
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    generation = load_json(PHASE2_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE2_DIR / "repetition_probe.json")
    leak = load_json(PHASE2_DIR / "internal_leak_probe.json")
    short = load_json(PHASE2_DIR / "short_output_probe.json")
    eval_losses = load_jsonl(PHASE2_DIR / "eval_loss_by_checkpoint.jsonl")
    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []
    artifact_counts = Counter()
    exact_rows: list[str] = []
    residual_examples: list[dict[str, Any]] = []
    for sample in samples:
        row_id = str(sample.get("row_id"))
        generated = str(sample.get("generated_text") or "")
        target = str(sample.get("target_text") or "")
        if sample.get("exact_match"):
            exact_rows.append(row_id)
        for marker in ["checkedier", "re2PEP", "PEPE", "introduceive", "evidence is"]:
            if marker in generated and marker not in target:
                artifact_counts[marker] += 1
        if not sample.get("target_prefix_match"):
            residual_examples.append(
                {
                    "row_id": row_id,
                    "split": sample.get("split"),
                    "prefix_words": len(str(sample.get("generation_prefix_text") or "").split()),
                    "prefix": sample.get("generation_prefix_text"),
                    "generated": generated[:180],
                    "target": target[:180],
                    "boundary_match": (sample.get("boundary_next_token") or {}).get("match"),
                    "stopped_on_eos": sample.get("stopped_on_eos"),
                    "degenerate_repetition": sample.get("degenerate_repetition"),
                }
            )

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9611_safety_probe_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9611_quality_gate_not_failed_as_expected")
    if generation.get("generation_prefix_start_rate") != 1.0:
        failures.append("prefix_start_regressed")
    if (repetition.get("degenerate_repetition_rate") or 0.0) > 0.25:
        failures.append("repetition_not_sufficiently_reduced")
    if len(exact_rows) == 0:
        failures.append("no_exact_rows_after_ladder")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "stage9611_quality_gate": source.get("metrics", {}).get("quality_gate"),
        "phase1_eval_suffix_choice_exact": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact"),
        "phase1_strict_suffix_choice_exact": source.get("metrics", {}).get("phase1_strict_suffix_choice_exact"),
        "phase2_contentful_generation_rate": generation.get("contentful_rate"),
        "phase2_target_prefix_match_rate": generation.get("target_prefix_match_rate"),
        "phase2_generation_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "phase2_boundary_next_token_match_rate": generation.get("boundary_next_token_match_rate"),
        "phase2_degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "phase2_unterminated_rate": repetition.get("unterminated_rate"),
        "phase2_internal_leak_rows": leak.get("generated_internal_token_rows"),
        "phase2_short_or_junk_rows": short.get("short_or_junk_rows"),
        "exact_rows": exact_rows,
        "exact_row_count": len(exact_rows),
        "artifact_counts": dict(artifact_counts),
        "eval_loss_by_split": {str(row.get("split")): row.get("loss") for row in eval_losses},
        "residual_examples": residual_examples[:10],
        "improvement_vs_stage9607": {
            "contentful_rate": "0.1667 -> 0.4167",
            "target_prefix_match_rate": "0.0 -> 0.1667",
            "degenerate_repetition_rate": "0.8333 -> 0.1667",
            "prefix_start_rate": "1.0 -> 1.0",
        },
        "root_cause": {
            "suffix_ladder_reduced_repetition": True,
            "remaining_failure_is_phrase_substitution_and_token_artifact": True,
            "needs_phrase_level_suffix_support_or_tokenization_guard": True,
            "do_not_reopen_decoder_ce_or_runtime": True,
        },
        "recommended_patch": {
            "stage9613": "build_phrase_level_suffix_support_manifest",
            "requirements": [
                "target high-loss phrase families: localized repair step, relevant repair region, checked verifier condition, wrapper plan",
                "add explicit anti-artifact negatives for checkedier/re2PEP/introduceive/evidence-is substitution",
                "preserve active_generation_prefix_span and post-prefix loss masking",
                "keep decoder_ce/runtime/Gemma/harness/export closed",
                "contract-only preflight before any execution",
            ],
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9613 phrase-level suffix support/anti-artifact manifest, then run contract-only preflight before another tiny probe."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Stage9611 suffix ladder improved repetition and produced exact rows, but residual failures are phrase substitutions and tokenizer-like artifacts rather than controller/prefix failures.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9612 Suffix Ladder Residual Failure Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Exact rows: `{audit['exact_row_count']}`",
        f"Contentful rate: `{audit['phase2_contentful_generation_rate']}`",
        f"Target prefix match rate: `{audit['phase2_target_prefix_match_rate']}`",
        f"Repetition rate: `{audit['phase2_degenerate_repetition_rate']}`",
        f"Artifact counts: `{audit['artifact_counts']}`",
        "",
        "Finding: the suffix ladder helped, but the remaining blocker is phrase-level substitution and tokenizer-like artifacts, not suffix-choice control or prefix priming.",
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
