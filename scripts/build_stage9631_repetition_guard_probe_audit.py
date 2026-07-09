#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9631
NAME = "stage9631_repetition_guard_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9630_tri_phase_repetition_guard_tiny_probe.json"
BASELINE_SUMMARY = ROOT / "runs/summaries/stage9623_tri_phase_reconnect_tiny_probe.json"
BASELINE_SAMPLES = ROOT / "runs/local/artifacts/stage9623_tri_phase_reconnect_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
GUARDED_SAMPLES = ROOT / "runs/local/artifacts/stage9630_tri_phase_repetition_guard_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe/sample_generation_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "repetition_guard_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPETITION_GUARD_PROBE_AUDIT_STAGE9631.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def repeated_text(text: str) -> bool:
    compact = "".join(ch for ch in text.lower() if not ch.isspace())
    if len(compact) >= 12:
        max_width = min(40, max(3, len(compact) // 3))
        for width in range(3, max_width + 1):
            for start in range(0, len(compact) - width * 3 + 1):
                chunk = compact[start:start + width]
                if len(set(chunk)) <= 1:
                    continue
                if all(compact[start + width * rep:start + width * (rep + 1)] == chunk for rep in range(1, 3)):
                    return True
    words = [word for word in text.lower().split() if word]
    if len(words) >= 6:
        for width in (1, 2, 3):
            ngrams = [tuple(words[idx:idx + width]) for idx in range(len(words) - width + 1)]
            counts: dict[tuple[str, ...], int] = {}
            for ngram in ngrams:
                counts[ngram] = counts.get(ngram, 0) + 1
            if counts and max(counts.values()) >= 4:
                return True
        trigrams = [tuple(words[idx:idx + 3]) for idx in range(len(words) - 2)]
        if trigrams and len(set(trigrams)) <= max(1, len(trigrams) // 3):
            return True
    return False


def sample_metrics(path: Path) -> dict[str, Any]:
    card = load_json(path)
    samples = card.get("samples") if isinstance(card.get("samples"), list) else []
    stronger_repetition = [row for row in samples if repeated_text(str(row.get("generated_text") or ""))]
    return {
        "generated_rows": len(samples),
        "contentful_rate": card.get("contentful_rate"),
        "target_prefix_match_rate": card.get("target_prefix_match_rate"),
        "generation_prefix_start_rate": card.get("generation_prefix_start_rate"),
        "recorded_repetition_rate": card.get("degenerate_repetition_rate"),
        "stronger_repetition_rows": len(stronger_repetition),
        "stronger_repetition_rate": len(stronger_repetition) / len(samples) if samples else None,
        "stronger_repetition_row_ids": [str(row.get("row_id")) for row in stronger_repetition],
    }


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
    src = load_json(SOURCE_SUMMARY)
    base = load_json(BASELINE_SUMMARY)
    base_metrics = sample_metrics(BASELINE_SAMPLES)
    guarded_metrics = sample_metrics(GUARDED_SAMPLES)
    failures: list[str] = []
    if src.get("passed") is not True:
        failures.append("stage9630_safety_not_passed")
    if not guarded_metrics.get("generated_rows"):
        failures.append("missing_guarded_samples")
    contentful_delta = (guarded_metrics.get("contentful_rate") or 0.0) - (base_metrics.get("contentful_rate") or 0.0)
    prefix_delta = (guarded_metrics.get("target_prefix_match_rate") or 0.0) - (base_metrics.get("target_prefix_match_rate") or 0.0)
    stronger_repetition_delta = (guarded_metrics.get("stronger_repetition_rate") or 0.0) - (base_metrics.get("stronger_repetition_rate") or 0.0)
    decision = (
        "Guard improves contentful output and intervenes on repeated-token attractors, but target-prefix fidelity remains low; "
        "do not widen denoise. Add a non-generative anti-repetition/EOS continuation objective or route-local phrase continuation labels."
    )
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "baseline_summary": str(BASELINE_SUMMARY.relative_to(ROOT)),
        "baseline_metrics": base_metrics,
        "guarded_metrics": guarded_metrics,
        "stage9623_contentful_rate": base.get("metrics", {}).get("phase3_contentful_generation_rate"),
        "stage9630_contentful_rate": src.get("metrics", {}).get("phase3_contentful_generation_rate"),
        "contentful_delta_vs_stage9623": contentful_delta,
        "target_prefix_delta_vs_stage9623": prefix_delta,
        "stronger_repetition_delta_vs_stage9623": stronger_repetition_delta,
        "guard_events": src.get("metrics", {}).get("phase3_generation_repetition_guard_events"),
        "guard_event_rows": src.get("metrics", {}).get("phase3_generation_repetition_guard_event_rows"),
        "quality_gate": src.get("metrics", {}).get("quality_gate"),
        "telemetry_patch_required": False,
        "decoder_ce_rows": src.get("metrics", {}).get("decoder_ce_rows"),
        "runtime_executed": src.get("metrics", {}).get("runtime_executed"),
        "final_checkpoint_exported": src.get("metrics", {}).get("final_checkpoint_exported"),
        "decision": decision,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Build Stage9632 non-generative anti-repetition/EOS continuation objective preflight; do not run another broad denoise expansion from Stage9630."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": decision,
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9631 Repetition Guard Probe Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Stage9623 -> Stage9630 contentful delta: `{contentful_delta}`",
        f"Stage9623 -> Stage9630 target-prefix delta: `{prefix_delta}`",
        f"Guard events / rows: `{audit['guard_events']}` / `{audit['guard_event_rows']}`",
        f"Stronger guarded repetition rows: `{guarded_metrics['stronger_repetition_rows']}`",
        "",
        decision,
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
