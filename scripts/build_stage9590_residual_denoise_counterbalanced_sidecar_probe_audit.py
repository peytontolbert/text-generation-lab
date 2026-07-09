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
STAGE = 9590
NAME = "stage9590_residual_denoise_counterbalanced_sidecar_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9589_residual_denoise_counterbalanced_sidecar_probe.json"
ROW_LOGITS = ROOT / "runs/local/artifacts/stage9589_residual_denoise_counterbalanced_sidecar_probe/counterbalanced_sidecar_probe/row_field_logits.jsonl"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "residual_denoise_counterbalanced_sidecar_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RESIDUAL_DENOISE_COUNTERBALANCED_SIDECAR_PROBE_AUDIT_STAGE9590.md"
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
    metrics = source.get("metrics") or {}
    rows = load_jsonl(ROW_LOGITS)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9589_not_passed")
    if metrics.get("pass_gate") is not False:
        failures.append("stage9589_pass_gate_not_false")
    low_conf_wrong = [r for r in rows if not r.get("correct") and not r.get("high_confidence_wrong")]
    high_conf_wrong = [r for r in rows if not r.get("correct") and r.get("high_confidence_wrong")]
    eval_exact = metrics.get("eval_suffix_choice_exact")
    strict_exact = metrics.get("strict_suffix_choice_exact")
    near_chance = eval_exact is not None and strict_exact is not None and eval_exact < 0.65 and strict_exact < 0.65
    if not near_chance:
        failures.append("stage9589_not_near_chance")
    if high_conf_wrong:
        failures.append("high_confidence_wrong_rows_present")

    audit = {
        "passed": not failures,
        "failures": failures,
        "source_summary": str(SOURCE_SUMMARY.relative_to(ROOT)),
        "eval_suffix_choice_exact": eval_exact,
        "strict_suffix_choice_exact": strict_exact,
        "near_chance_after_counterbalance": near_chance,
        "low_confidence_wrong_rows": len(low_conf_wrong),
        "high_confidence_wrong_rows": len(high_conf_wrong),
        "diagnosis": "counterbalanced sidecar removed shortcuts but the row surface is too noisy/weakly serialized for 80-step structured learning",
        "recommended_patch": "build a minimal verifier-evidence sidecar manifest with only language, route family, boundary_miss boolean, prefix_only boolean, and suffix_choice target",
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
        "decision": "The counterbalanced sidecar probe is safe but near chance, with low-confidence errors. Build a minimal verifier-evidence sidecar surface before rerunning.",
        "next_best_step": "Build and shortcut-audit a minimal residual sidecar manifest that removes noisy residual context keys and preserves only verifier decision evidence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9590 Residual Denoise Counterbalanced Sidecar Probe Audit", "", f"Passed: `{audit['passed']}`", f"Eval suffix choice exact: `{eval_exact}`", f"Strict suffix choice exact: `{strict_exact}`", "", "The counterbalanced sidecar is safe but near chance. Next: minimal verifier-evidence sidecar surface.", ""]), encoding="utf-8")
    update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "near_chance_after_counterbalance": near_chance, "failures": failures}, indent=2, sort_keys=True))
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
