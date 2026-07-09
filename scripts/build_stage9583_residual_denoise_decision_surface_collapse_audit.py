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
STAGE = 9583
NAME = "stage9583_residual_denoise_decision_surface_collapse_audit"
SOURCES = {
    "raw_boundary_contrast": ROOT / "runs/summaries/stage9576_residual_denoise_boundary_interleaved_capped_probe.json",
    "prefix_primed_literal": ROOT / "runs/summaries/stage9579_residual_denoise_boundary_prefix_primed_capped_probe.json",
    "neutral_yes_no": ROOT / "runs/summaries/stage9582_residual_denoise_neutral_boundary_decision_capped_probe.json",
}
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_decision_surface_collapse_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_DECISION_SURFACE_COLLAPSE_AUDIT_STAGE9583.md"
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    source_metrics: dict[str, dict[str, Any]] = {}
    for key, path in SOURCES.items():
        payload = load_json(path)
        if payload.get("passed") is not True:
            failures.append(f"{key}_not_passed")
        metrics = payload.get("metrics") or {}
        source_metrics[key] = {
            "summary": str(path.relative_to(ROOT)),
            "sample_balanced": metrics.get("sample_balanced"),
            "class_gate_passed": metrics.get("class_gate_passed"),
            "pred_counts": metrics.get("pred_counts"),
            "confusion": metrics.get("confusion"),
            "boundary_recall": metrics.get("boundary_recall"),
            "prefix_recall": metrics.get("prefix_recall"),
            "yes_recall": metrics.get("yes_recall"),
            "no_recall": metrics.get("no_recall"),
            "next_token_match_rate": metrics.get("boundary_next_token_match_rate"),
            "contentful_generation_rate": metrics.get("contentful_generation_rate"),
            "target_prefix_match_rate": metrics.get("target_prefix_match_rate"),
        }
        if metrics.get("sample_balanced") is not True:
            failures.append(f"{key}_sample_not_balanced")
        if metrics.get("class_gate_passed") is not False:
            failures.append(f"{key}_class_gate_not_failed")

    collapse_sequence = [
        source_metrics["raw_boundary_contrast"].get("pred_counts"),
        source_metrics["prefix_primed_literal"].get("pred_counts"),
        source_metrics["neutral_yes_no"].get("pred_counts"),
    ]
    collapse_pattern_confirmed = (
        collapse_sequence[0] == {"PREFIX": 16}
        and collapse_sequence[1] == {"BOUNDARY": 16}
        and collapse_sequence[2] == {"NO": 16}
    )
    if not collapse_pattern_confirmed:
        failures.append("collapse_pattern_not_confirmed")

    sidecar_required = collapse_pattern_confirmed and not failures
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_metrics": source_metrics,
        "collapse_pattern_confirmed": collapse_pattern_confirmed,
        "decoder_only_decision_surface_blocked": True,
        "structured_decision_sidecar_required": sidecar_required,
        "recommended_sidecar_fields": [
            "boundary_next_token_repair_required",
            "prefix_only_repair_required",
            "repair_scope_family",
            "verifier_residual_reason_class",
        ],
        "recommended_training_route": "structured_sidecar_then_denoise_render",
        "widening_authorized": False,
        "model_execution_authorized_next": False,
        "denoise_ce_training_authorized_next": False,
        "decoder_ce_training_authorized_next": False,
        "runtime_authorized": False,
        "promotion_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Three balanced denoise probes collapsed to a single class under three target surfaces. The route needs a structured decision sidecar before using denoise CE as the class decision mechanism.",
        "next_best_step": "Build a residual-denoise structured decision sidecar manifest for boundary_next_token_repair_required / prefix_only_repair_required, then use the sidecar output to gate denoise rendering.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9583 Residual Denoise Decision Surface Collapse Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Collapse pattern confirmed: `{collapse_pattern_confirmed}`",
                f"Structured decision sidecar required: `{sidecar_required}`",
                "",
                "Observed balanced-sample collapses:",
                "",
                "- Stage9576 raw contrast: all `PREFIX`",
                "- Stage9579 prefix-primed literal contrast: all `BOUNDARY`",
                "- Stage9582 neutral YES/NO contrast: all `NO`",
                "",
                "Next: train a structured sidecar for the residual repair decision, then render denoise text from that decision.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "collapse_pattern_confirmed": collapse_pattern_confirmed, "structured_decision_sidecar_required": sidecar_required, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
