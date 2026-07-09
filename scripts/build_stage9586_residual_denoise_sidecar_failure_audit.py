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
STAGE = 9586
NAME = "stage9586_residual_denoise_sidecar_failure_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9585_residual_denoise_structured_decision_sidecar_probe.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_sidecar_failure_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_SIDECAR_FAILURE_AUDIT_STAGE9586.md"
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
    source = load_json(SOURCE_SUMMARY)
    metrics = source.get("metrics") or {}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9585_not_passed")
    if metrics.get("pass_gate") is not False:
        failures.append("stage9585_pass_gate_not_false")
    if metrics.get("eval_suffix_choice_exact") != 0.5:
        failures.append("unexpected_eval_exact")
    if metrics.get("strict_suffix_choice_exact") != 0.8:
        failures.append("unexpected_strict_exact")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "eval_suffix_choice_exact": metrics.get("eval_suffix_choice_exact"),
        "strict_suffix_choice_exact": metrics.get("strict_suffix_choice_exact"),
        "pass_gate": metrics.get("pass_gate"),
        "safe_probe": True,
        "quality_passed": False,
        "sidecar_not_ready_for_denoise_render_gate": True,
        "recommended_patch": "add counterbalanced residual sidecar rows where the same language/route/evidence shell supports both suffix choices and audit feature baselines before rerunning",
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
        "decision": "The structured suffix_choice sidecar ran safely but did not meet the 0.95 eval/strict exactness gate, so it is not ready to gate denoise rendering.",
        "next_best_step": "Build counterbalanced residual sidecar rows and shortcut baselines before rerunning the suffix_choice sidecar probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9586 Residual Denoise Sidecar Failure Audit", "", f"Passed: `{audit['passed']}`", f"Eval suffix choice exact: `{audit['eval_suffix_choice_exact']}`", f"Strict suffix choice exact: `{audit['strict_suffix_choice_exact']}`", "", "The sidecar is safe but not quality-passing. Next: counterbalanced sidecar rows and shortcut baselines.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "quality_passed": audit["quality_passed"], "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
