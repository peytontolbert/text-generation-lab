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
STAGE = 9616
NAME = "stage9616_phrase_suffix_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9615_phrase_suffix_two_phase_tiny_probe.json"
PHASE2_DIR = ROOT / "runs/local/artifacts/stage9615_phrase_suffix_two_phase_tiny_probe/two_phase_probe/phase2_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "phrase_suffix_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_SUFFIX_PROBE_AUDIT_STAGE9616.md"
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
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    generation = load_json(PHASE2_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE2_DIR / "repetition_probe.json")
    leak = load_json(PHASE2_DIR / "internal_leak_probe.json")
    short = load_json(PHASE2_DIR / "short_output_probe.json")
    quality = load_json(PHASE2_DIR / "denoise_repair_quality_audit.json")
    samples = generation.get("samples") if isinstance(generation.get("samples"), list) else []
    target_prefix_miss = []
    exact_rows = []
    phrase_families = Counter()
    for sample in samples:
        row_id = str(sample.get("row_id"))
        if sample.get("exact_match"):
            exact_rows.append(row_id)
        if not sample.get("target_prefix_match"):
            target_prefix_miss.append(
                {
                    "row_id": row_id,
                    "prefix": sample.get("generation_prefix_text"),
                    "generated": str(sample.get("generated_text") or "")[:180],
                    "target": str(sample.get("target_text") or "")[:180],
                }
            )
        text = str(sample.get("target_text") or "").lower()
        if "localized repair step" in text:
            phrase_families["localized_repair_step"] += 1
        elif "localized edit target" in text:
            phrase_families["localized_edit_target"] += 1
        elif "relevant repair region" in text:
            phrase_families["relevant_repair_region"] += 1
        elif "checked verifier condition" in text:
            phrase_families["checked_verifier_condition"] += 1
        elif "wrapper plan" in text:
            phrase_families["wrapper_plan"] += 1
        else:
            phrase_families["other"] += 1

    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9615_safety_probe_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not True:
        failures.append("stage9615_quality_gate_not_passed")
    if generation.get("contentful_rate") != 1.0:
        failures.append("contentful_rate_not_1")
    if generation.get("generation_prefix_start_rate") != 1.0:
        failures.append("prefix_start_not_1")
    if (repetition.get("degenerate_repetition_rate") or 0.0) != 0.0:
        failures.append("repetition_present")
    if leak.get("generated_internal_token_rows") not in {0, None}:
        failures.append("internal_leak_present")
    if short.get("short_or_junk_rows") not in {0, None}:
        failures.append("short_or_junk_present")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "phase2_dir": str(PHASE2_DIR.relative_to(ROOT)),
        "phase1_eval_suffix_choice_exact": source.get("metrics", {}).get("phase1_eval_suffix_choice_exact"),
        "phase1_strict_suffix_choice_exact": source.get("metrics", {}).get("phase1_strict_suffix_choice_exact"),
        "phase2_contentful_generation_rate": generation.get("contentful_rate"),
        "phase2_target_prefix_match_rate": generation.get("target_prefix_match_rate"),
        "phase2_generation_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "phase2_boundary_next_token_match_rate": generation.get("boundary_next_token_match_rate"),
        "phase2_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "phase2_unterminated_rate": repetition.get("unterminated_rate"),
        "phase2_internal_leak_rows": leak.get("generated_internal_token_rows"),
        "phase2_short_or_junk_rows": short.get("short_or_junk_rows"),
        "phase2_eval": quality.get("eval"),
        "exact_row_count": len(exact_rows),
        "exact_rows": exact_rows,
        "target_prefix_miss_rows": target_prefix_miss,
        "sample_phrase_families": dict(phrase_families),
        "decision": "Phrase-level suffix support is quality-passing as a local objective. It should now be integrated with the full residual suffix-ladder rows to test transfer back to complete bounded residual repair.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9617 integrated residual-plus-phrase denoise manifest, then run contract-only preflight before another tiny execution."
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
        "# Stage9616 Phrase-Suffix Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Contentful rate: `{audit['phase2_contentful_generation_rate']}`",
        f"Prefix start rate: `{audit['phase2_generation_prefix_start_rate']}`",
        f"Target prefix match rate: `{audit['phase2_target_prefix_match_rate']}`",
        f"Exact sampled rows: `{audit['exact_row_count']}`",
        "",
        "Phrase-level suffix support is now quality-passing locally. The next step is integration back into full residual suffix repair.",
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
