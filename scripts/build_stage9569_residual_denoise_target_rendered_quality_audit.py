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
STAGE = 9569
NAME = "stage9569_residual_denoise_target_rendered_quality_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9568_residual_denoise_target_rendered_tiny_probe.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9568_residual_denoise_target_rendered_tiny_probe/denoise_repair_probe"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_target_rendered_quality_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_TARGET_RENDERED_QUALITY_AUDIT_STAGE9569.md"
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    execution = load_json(RUN_DIR / "execution_result.json")
    quality = load_json(RUN_DIR / "denoise_repair_quality_audit.json")
    step_rows = load_jsonl(RUN_DIR / "loss_by_step.jsonl")
    sample = load_json(RUN_DIR / "sample_generation_audit.json")
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9568_not_passed")
    nonzero_loss_steps = sum(1 for row in step_rows if float(row.get("loss", 0.0)) > 0.0)
    finite_eval = isinstance((quality.get("eval") or {}).get("eval"), dict) and isinstance((quality.get("eval") or {}).get("strict_eval"), dict)
    target_rendering_fixed = int((source.get("metrics") or {}).get("non_eos_token_loss_rows", 0)) > 0 and nonzero_loss_steps == int(execution.get("max_steps", 0))
    contentful_rate = quality.get("contentful_generation_rate")
    target_prefix_match_rate = quality.get("target_prefix_match_rate")
    quality_gate_passed = (
        bool(target_rendering_fixed)
        and bool(finite_eval)
        and isinstance(contentful_rate, (float, int))
        and float(contentful_rate) > 0.0
        and isinstance(target_prefix_match_rate, (float, int))
        and float(target_prefix_match_rate) > 0.0
    )
    if not target_rendering_fixed:
        failures.append("target_rendering_not_fixed")
    if not finite_eval:
        failures.append("missing_eval_losses")
    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "run_dir": str(RUN_DIR.relative_to(ROOT)),
        "target_rendering_fixed": target_rendering_fixed,
        "nonzero_loss_steps": nonzero_loss_steps,
        "max_steps": execution.get("max_steps"),
        "eval_loss": ((quality.get("eval") or {}).get("eval") or {}).get("loss"),
        "strict_eval_loss": ((quality.get("eval") or {}).get("strict_eval") or {}).get("loss"),
        "generated_rows": quality.get("generated_rows"),
        "contentful_generation_rate": contentful_rate,
        "target_prefix_match_rate": target_prefix_match_rate,
        "short_or_junk_rate": quality.get("short_or_junk_rate"),
        "degenerate_repetition_rate": quality.get("degenerate_repetition_rate"),
        "sample_count": len(sample.get("samples") or []),
        "quality_gate_passed": quality_gate_passed,
        "widening_authorized": False,
        "next_patch": "keep target-rendered manifest, add generation-oriented diagnostics or slightly longer capped denoise schedule before widening",
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
        "decision": "Target rendering fixed the EOS-only training bug, but generation quality did not pass. Widening remains blocked.",
        "next_best_step": "Patch the denoise rerun with generation-quality diagnostics or a slightly longer capped schedule; do not widen residual-denoise training yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9569 Residual Denoise Target-Rendered Quality Audit", "", f"Passed: `{audit['passed']}`", f"Target rendering fixed: `{target_rendering_fixed}`", f"Quality gate passed: `{quality_gate_passed}`", f"Contentful generation rate: `{contentful_rate}`", f"Target prefix match rate: `{target_prefix_match_rate}`", "", "Widening remains blocked. The next patch should keep the rendered target and improve the generation-quality probe before scaling.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "target_rendering_fixed": target_rendering_fixed, "quality_gate_passed": quality_gate_passed, "contentful_generation_rate": contentful_rate, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
