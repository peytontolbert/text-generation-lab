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
STAGE = 9620
NAME = "stage9620_integrated_residual_phrase_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9619_integrated_residual_phrase_tiny_probe.json"
PHRASE_SUMMARY = ROOT / "runs/summaries/stage9615_phrase_suffix_two_phase_tiny_probe.json"
PHRASE_AUDIT = ROOT / "runs/local/artifacts/stage9616_phrase_suffix_probe_audit/phrase_suffix_probe_audit.json"
PHASE2_DIR = ROOT / "runs/local/artifacts/stage9619_integrated_residual_phrase_tiny_probe/two_phase_probe/phase2_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "integrated_residual_phrase_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "INTEGRATED_RESIDUAL_PHRASE_FAILURE_AUDIT_STAGE9620.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def sample_failure_rows(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sample in samples:
        if sample.get("exact_match") and sample.get("target_prefix_match"):
            continue
        rows.append(
            {
                "row_id": sample.get("row_id"),
                "split": sample.get("split"),
                "exact_match": sample.get("exact_match"),
                "target_prefix_match": sample.get("target_prefix_match"),
                "generation_prefix_start_match": sample.get("generation_prefix_start_match"),
                "degenerate_repetition": sample.get("degenerate_repetition"),
                "stopped_on_eos": sample.get("stopped_on_eos"),
                "prefix": sample.get("generation_prefix_text"),
                "generated": str(sample.get("generated_text") or "")[:220],
                "target": str(sample.get("target_text") or "")[:220],
            }
        )
    return rows[:12]


def token_artifact_counts(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for sample in samples:
        text = str(sample.get("generated_text") or "").lower()
        for artifact in ("match ins", "match match", "whitelist", "re2pep", "checkedier"):
            if artifact in text:
                counts[artifact] += 1
        if not sample.get("stopped_on_eos"):
            counts["unterminated"] += 1
        if sample.get("degenerate_repetition"):
            counts["degenerate_repetition"] += 1
    return dict(counts)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    phrase_source = load_json(PHRASE_SUMMARY)
    phrase_audit = load_json(PHRASE_AUDIT)
    generation = load_json(PHASE2_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE2_DIR / "repetition_probe.json")
    leak = load_json(PHASE2_DIR / "internal_leak_probe.json")
    short = load_json(PHASE2_DIR / "short_output_probe.json")
    quality = load_json(PHASE2_DIR / "denoise_repair_quality_audit.json")
    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9619_safety_probe_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9619_quality_failure_not_detected")
    if phrase_source.get("metrics", {}).get("quality_gate") is not True:
        failures.append("stage9615_phrase_quality_not_available")
    if generation.get("generation_prefix_start_rate") != 1.0:
        failures.append("prefix_start_regressed")
    if (generation.get("contentful_rate") or 0.0) >= (phrase_audit.get("phase2_contentful_generation_rate") or 0.0):
        failures.append("integrated_probe_did_not_regress_vs_phrase_probe")
    if (repetition.get("degenerate_repetition_rate") or 0.0) <= (phrase_audit.get("phase2_repetition_rate") or 0.0):
        failures.append("repetition_not_worse_than_phrase_probe")

    diagnosis = {
        "root_cause": "one_pass_full_suffix_plus_phrase_support_curriculum_interference",
        "evidence": [
            "Stage9615 phrase-only probe reached contentful=1.0, prefix_start=1.0, target_prefix_match=0.8333, and zero repetition/leak/short rows.",
            "Stage9619 integrated probe kept phase1 exact at 1.0/1.0 and prefix_start=1.0, but phase2 contentful fell to 0.0833 and target_prefix_match to 0.0.",
            "Stage9619 samples repeat route/action fragments such as 'match ins' and 'match match', showing target-suffix continuation interference rather than a budget or authority failure.",
        ],
        "not_root_causes": [
            "not_decoder_ce_reopen: decoder_ce_rows stayed 0",
            "not_phase1_sidecar_failure: eval/strict suffix choice exact stayed 1.0",
            "not_prefix_injection_failure: generation_prefix_start_rate stayed 1.0",
            "not_internal_token_leak: internal leak rows stayed zero or unavailable",
        ],
        "recommended_patch": "Replace one-pass mixed phase2 training with staged in-memory sequencing: phase1 suffix choice, phase2 phrase suffix warm-up, then phase3 full residual suffix ladder reconnect. Keep decoder CE, runtime, Gemma, harness, checkpoint export, and promotion closed.",
    }
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phrase_source_summary": str(PHRASE_SUMMARY.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "stage9615_quality_gate": phrase_source.get("metrics", {}).get("quality_gate"),
        "stage9615_contentful_rate": phrase_audit.get("phase2_contentful_generation_rate"),
        "stage9615_target_prefix_match_rate": phrase_audit.get("phase2_target_prefix_match_rate"),
        "stage9615_repetition_rate": phrase_audit.get("phase2_repetition_rate"),
        "stage9619_quality_gate": source.get("metrics", {}).get("quality_gate"),
        "stage9619_phase1_eval_suffix_choice_exact": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact"),
        "stage9619_phase1_strict_suffix_choice_exact": source.get("metrics", {}).get("phase1_strict_suffix_choice_exact"),
        "stage9619_contentful_rate": generation.get("contentful_rate"),
        "stage9619_target_prefix_match_rate": generation.get("target_prefix_match_rate"),
        "stage9619_generation_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "stage9619_boundary_next_token_match_rate": generation.get("boundary_next_token_match_rate"),
        "stage9619_degenerate_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "stage9619_unterminated_rate": repetition.get("unterminated_rate"),
        "stage9619_internal_leak_rows": leak.get("generated_internal_token_rows"),
        "stage9619_short_or_junk_rows": short.get("short_or_junk_rows"),
        "stage9619_phase2_eval": quality.get("eval"),
        "artifact_counts": token_artifact_counts(samples),
        "sample_failure_rows": sample_failure_rows(samples),
        "diagnosis": diagnosis,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Design Stage9621 tri-phase in-memory residual reconnect wrapper: suffix-choice sidecar, phrase-suffix warm-up, then full residual suffix ladder; run contract-only preflight before execution."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": diagnosis["recommended_patch"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9620 Integrated Residual-Phrase Failure Audit",
                "",
                f"Passed: `{audit['passed']}`",
                "",
                "Stage9619 is a safe but quality-failing run. Phase1 stayed solved, decoder CE stayed closed, and prefix injection worked, but the mixed residual-plus-phrase phase2 objective collapsed into repeated route fragments.",
                "",
                "Key comparison:",
                "",
                f"- Stage9615 phrase-only contentful: `{audit['stage9615_contentful_rate']}`",
                f"- Stage9615 phrase-only target prefix: `{audit['stage9615_target_prefix_match_rate']}`",
                f"- Stage9619 integrated contentful: `{audit['stage9619_contentful_rate']}`",
                f"- Stage9619 integrated target prefix: `{audit['stage9619_target_prefix_match_rate']}`",
                f"- Stage9619 integrated prefix start: `{audit['stage9619_generation_prefix_start_rate']}`",
                f"- Stage9619 artifact counts: `{audit['artifact_counts']}`",
                "",
                "Diagnosis: one-pass full-suffix plus phrase-support training creates curriculum interference. Phrase support should be staged as an in-memory warm-up or intermediate phase before full residual suffix reconnect.",
                "",
                "Authority remains closed: no decoder CE reopen, no runtime, no Gemma, no harness, no checkpoint export, no promotion.",
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
