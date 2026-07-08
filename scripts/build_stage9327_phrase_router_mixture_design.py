#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9327
NAME = "stage9327_phrase_router_mixture_design"
SOURCE_A = ROOT / "runs/summaries/stage9324_phrase_a_probe_audit.json"
SOURCE_B = ROOT / "runs/summaries/stage9326_phrase_b_probe_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DESIGN = OUT_DIR / "phrase_router_mixture_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PHRASE_ROUTER_MIXTURE_DESIGN_STAGE9327.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    a = load_json(SOURCE_A)
    b = load_json(SOURCE_B)
    a_metrics = a.get("metrics") if isinstance(a.get("metrics"), dict) else {}
    b_metrics = b.get("metrics") if isinstance(b.get("metrics"), dict) else {}
    failures: list[str] = []
    if a.get("passed") is not True or a_metrics.get("quality_gate_passed") is not True:
        failures.append("phrase_a_not_clean")
    if b.get("passed") is not True or b_metrics.get("quality_gate_passed") is not True:
        failures.append("phrase_b_not_clean")
    design = {
        "passed": not failures,
        "failures": failures,
        "evidence": {
            "phrase_a_exact_rate": a_metrics.get("exact_match_rate"),
            "phrase_b_exact_rate": b_metrics.get("exact_match_rate"),
            "phrase_a_target_prefix_match_rate": a_metrics.get("target_prefix_match_rate"),
            "phrase_b_target_prefix_match_rate": b_metrics.get("target_prefix_match_rate"),
            "prior_combined_stage": 9321,
            "prior_combined_phrase_a_exact_rate": ((load_json(ROOT / "runs/summaries/stage9321_phrase_completion_probe_audit.json").get("metrics") or {}).get("by_phrase") or {}).get("phrase_a", {}).get("exact_rate"),
            "prior_combined_phrase_b_exact_rate": ((load_json(ROOT / "runs/summaries/stage9321_phrase_completion_probe_audit.json").get("metrics") or {}).get("by_phrase") or {}).get("phrase_b", {}).get("exact_rate"),
        },
        "diagnosis": "phrase_a_and_phrase_b_are_individually_learnable_but_interfere_when_mixed_without_a_router_or_semantic_discriminator",
        "recommended_patch": {
            "manifest_name": "phrase_router_mixture_manifest",
            "rows": [
                "phrase_router_head_rows: prefix/context -> phrase_a|phrase_b|phrase_c",
                "phrase_conditioned_denoise_rows: include opaque phrase route plus non-label semantic discriminator",
                "cross_negative_rows: phrase_a prefix with phrase_b forbidden only as loss-negative telemetry, not visible target text",
                "balanced_mixture_rows: equal train/eval/strict coverage by phrase family and prefix length",
            ],
            "required_model_inputs": [
                "opaque_phrase_route_id",
                "semantic_surface_kind: dependency_handle|patch_operator_argument|constant_argument",
                "anchor_object_kind",
                "language_family",
                "active_generation_prefix_span",
            ],
            "forbidden_model_inputs": [
                "literal target suffix",
                "external phrase label text",
                "bad continuation literal outside corruption rows",
            ],
            "probe_gate": {
                "phrase_router_exact_by_split": "1.0 for tiny probe",
                "combined_exact_match_rate": "1.0 before rejoining Stage9310 ladder",
                "decoder_ce_rows": 0,
                "runtime_gemma_harness": "closed",
            },
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    DESIGN.write_text(json.dumps(design, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": design["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **design},
        "artifacts": {"design": str(DESIGN.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Do not merge phrase A/B as flat denoise rows. Add phrase routing or non-label semantic discriminators first.",
        "next_best_step": "Build Stage9328 phrase-router mixture manifest with opaque route IDs and semantic discriminators, then run a tiny combined phrase-router probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9327 Phrase Router Mixture Design",
        "",
        f"Passed: `{design['passed']}`",
        "Phrase A and phrase B both pass in isolation, but they fail when mixed without a route/discriminator.",
        "Next patch: build a phrase-router mixture manifest with opaque route IDs plus non-label semantic discriminators.",
        "Decoder CE, runtime, Gemma, harness, source/body emission, scoring, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": {"diagnosis": design["diagnosis"], "failures": failures}}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
