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
STAGE = 9599
NAME = "stage9599_suffix_choice_residual_denoise_reconnect_design"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9598_structured_head_architecture_contract.json"
SIDECAR_SUMMARY = ROOT / "runs/summaries/stage9597_encoder_rope_minimal_sidecar_probe.json"
SIDECAR_MANIFEST = ROOT / "runs/local/artifacts/stage9591_residual_denoise_minimal_sidecar_manifest/residual_denoise_minimal_sidecar_manifest.jsonl"
DENOISE_SOURCE_MANIFEST = ROOT / "runs/local/artifacts/stage9566_residual_denoise_target_rendered_manifest/residual_denoise_target_rendered_manifest.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "suffix_choice_residual_denoise_reconnect_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SUFFIX_CHOICE_RESIDUAL_DENOISE_RECONNECT_DESIGN_STAGE9599.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


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
    sidecar = load_json(SIDECAR_SUMMARY)
    sidecar_rows = load_jsonl(SIDECAR_MANIFEST)
    denoise_rows = load_jsonl(DENOISE_SOURCE_MANIFEST)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9598_not_passed")
    sidecar_metrics = sidecar.get("metrics") if isinstance(sidecar.get("metrics"), dict) else {}
    if sidecar_metrics.get("eval_suffix_choice_exact") != 1.0 or sidecar_metrics.get("strict_suffix_choice_exact") != 1.0:
        failures.append("sidecar_not_quality_passing")
    if sidecar_metrics.get("max_frozen_bucket_delta") != 0.0:
        failures.append("sidecar_frozen_bucket_delta_nonzero")
    if len(sidecar_rows) != 96:
        failures.append("sidecar_manifest_row_count_not_96")
    if len(denoise_rows) != 41:
        failures.append("denoise_source_row_count_not_41")
    if any(any((row.get("authority") or {}).values()) for row in sidecar_rows + denoise_rows):
        failures.append("authority_rows_present")

    design = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "sidecar_summary": str(SIDECAR_SUMMARY.relative_to(ROOT)),
        "sidecar_manifest": str(SIDECAR_MANIFEST.relative_to(ROOT)),
        "denoise_source_manifest": str(DENOISE_SOURCE_MANIFEST.relative_to(ROOT)),
        "sidecar_rows": len(sidecar_rows),
        "denoise_source_rows": len(denoise_rows),
        "required_architecture_contracts": {
            "encoder_rope_for_structured_heads": True,
            "structured_phase_freezes_decoder_lm_head_embeddings": True,
            "no_final_checkpoint_export": True,
            "cleanup_via_safe_cleanup_only": True,
        },
        "recommended_probe_shape": {
            "mode_needed": "two_phase_suffix_choice_denoise_reconnect_probe",
            "phase_1": {
                "objective": "suffix_choice_ce",
                "manifest": str(SIDECAR_MANIFEST.relative_to(ROOT)),
                "decoder_ce_weight": 0.0,
                "denoise_weight": 0.0,
                "structured_aux_weight": 1.0,
                "restore_best_structured_state": True,
                "export_checkpoint": False,
            },
            "phase_2": {
                "objective": "denoise_ce",
                "manifest": str(DENOISE_SOURCE_MANIFEST.relative_to(ROOT)),
                "decoder_ce_weight": 0.0,
                "denoise_weight": 1.0,
                "structured_aux_weight": 0.0,
                "condition_on": "effective_suffix_choice_from_phase_1_or_deterministic_verifier_overlay",
                "generation_audit_required": True,
                "export_checkpoint": False,
            },
        },
        "pass_gates_for_future_execution": {
            "phase_1_eval_suffix_choice_exact_min": 0.95,
            "phase_1_strict_suffix_choice_exact_min": 0.95,
            "phase_1_frozen_decoder_lm_head_embedding_delta": 0.0,
            "phase_2_contentful_rate": 1.0,
            "phase_2_short_junk_rows": 0,
            "phase_2_repetition_rows": 0,
            "phase_2_internal_leak_rows": 0,
            "phase_2_boundary_and_prefix_recall_min": 0.95,
        },
        "not_authorized_yet": [
            "decoder_ce",
            "runtime",
            "source_or_body_emission",
            "checkpoint_export",
            "controller_merge",
            "promotion",
        ],
        "authority": dict(AUTHORITY_CLOSED),
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Implement a contract-only two-phase suffix-choice plus residual-denoise reconnect wrapper; do not execute nonzero denoise until that wrapper audit passes."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Designed the reconnect path from the now-passing suffix_choice sidecar to residual denoise rendering as a two-phase closed-boundary probe.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9599 Suffix-Choice Residual Denoise Reconnect Design",
        "",
        f"Passed: `{design['passed']}`",
        f"Sidecar rows: `{len(sidecar_rows)}`",
        f"Denoise source rows: `{len(denoise_rows)}`",
        "",
        "Design: run a two-phase closed probe. Phase 1 trains the `suffix_choice_ce` controller under encoder RoPE and frozen decoder/export buckets. Phase 2 uses that effective choice to condition residual-denoise rendering with decoder CE/runtime/export still closed.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": design["passed"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if not design["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
