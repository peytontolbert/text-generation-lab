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
STAGE = 9628
NAME = "stage9628_hard_phrase_tri_phase_regression_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9627_hard_phrase_tri_phase_tiny_probe.json"
BASELINE_SUMMARY = ROOT / "runs/summaries/stage9623_tri_phase_reconnect_tiny_probe.json"
PHASE3_DIR = ROOT / "runs/local/artifacts/stage9627_hard_phrase_tri_phase_tiny_probe/tri_phase_probe/phase3_full_residual_denoise_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "hard_phrase_tri_phase_regression_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARD_PHRASE_TRI_PHASE_REGRESSION_AUDIT_STAGE9628.md"
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
    baseline = load_json(BASELINE_SUMMARY)
    generation = load_json(PHASE3_DIR / "sample_generation_audit.json")
    repetition = load_json(PHASE3_DIR / "repetition_probe.json")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9627_safety_not_passed")
    if source.get("metrics", {}).get("quality_gate") is not False:
        failures.append("stage9627_quality_failure_not_recorded")
    src = source.get("metrics") if isinstance(source.get("metrics"), dict) else {}
    base = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    regression = {
        "contentful_delta_vs_stage9623": (src.get("phase3_contentful_generation_rate") or 0.0) - (base.get("phase3_contentful_generation_rate") or 0.0),
        "target_prefix_delta_vs_stage9623": (src.get("phase3_target_prefix_match_rate") or 0.0) - (base.get("phase3_target_prefix_match_rate") or 0.0),
        "repetition_delta_vs_stage9623": (repetition.get("degenerate_repetition_rate") or 0.0) - 0.5,
    }
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "baseline_summary": str(BASELINE_SUMMARY.relative_to(ROOT)),
        "stage9623_contentful_rate": base.get("phase3_contentful_generation_rate"),
        "stage9623_target_prefix_match_rate": base.get("phase3_target_prefix_match_rate"),
        "stage9627_contentful_rate": src.get("phase3_contentful_generation_rate"),
        "stage9627_target_prefix_match_rate": src.get("phase3_target_prefix_match_rate"),
        "stage9627_repetition_rate": repetition.get("degenerate_repetition_rate"),
        "stage9627_unterminated_rate": repetition.get("unterminated_rate"),
        "stage9627_prefix_start_rate": generation.get("generation_prefix_start_rate"),
        "stage9627_boundary_next_token_match_rate": generation.get("boundary_next_token_match_rate"),
        "regression": regression,
        "decision": "Reject Stage9625 hard-phrase warm-up as a curriculum branch. It worsened contentful generation and repetition despite preserving safety and boundary-prefix injection.",
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Return to the Stage9623 tri-phase baseline and design a non-generative anti-repetition/EOS continuation objective or decoding-time repetition guard audit before further denoise execution."
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
        "# Stage9628 Hard-Phrase Tri-Phase Regression Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Stage9623 contentful / prefix: `{audit['stage9623_contentful_rate']}` / `{audit['stage9623_target_prefix_match_rate']}`",
        f"Stage9627 contentful / prefix: `{audit['stage9627_contentful_rate']}` / `{audit['stage9627_target_prefix_match_rate']}`",
        f"Stage9627 repetition / unterminated: `{audit['stage9627_repetition_rate']}` / `{audit['stage9627_unterminated_rate']}`",
        "",
        "Decision: reject Stage9625 hard-phrase warm-up as a curriculum branch. It preserved safety but created a stronger repetition attractor.",
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
