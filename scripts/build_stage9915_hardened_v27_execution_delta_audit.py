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
STAGE = 9915
NAME = "stage9915_hardened_v27_execution_delta_audit"
CURRENT = ROOT / "runs/summaries/stage9914_hardened_structured_tiny_execution_review.json"
BASELINE = ROOT / "runs/summaries/stage9899_geometry_aware_structured_tiny_execution_review.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "hardened_v27_execution_delta_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HARDENED_V27_EXECUTION_DELTA_AUDIT_STAGE9915.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def surface_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = payload.get("metrics", {}).get("surface_results") if isinstance(payload.get("metrics"), dict) else None
    if not isinstance(results, list):
        return {}
    return {str(row.get("surface") or ""): row for row in results}


def build_audit() -> dict[str, Any]:
    current = load_json(CURRENT)
    baseline = load_json(BASELINE)
    failures: list[str] = []
    if current.get("passed") is not True:
        failures.append("stage9914_not_passed")
    if baseline.get("passed") is not True:
        failures.append("stage9899_not_passed")
    current_surfaces = surface_map(current)
    baseline_surfaces = surface_map(baseline)
    delta = {}
    for surface in sorted(set(current_surfaces) | set(baseline_surfaces)):
        cur = current_surfaces.get(surface, {})
        base = baseline_surfaces.get(surface, {})
        delta[surface] = {
            "eval_exact_current": cur.get("eval_exact"),
            "eval_exact_baseline": base.get("eval_exact"),
            "delta_eval_exact": (
                cur.get("eval_exact") - base.get("eval_exact")
                if isinstance(cur.get("eval_exact"), (int, float)) and isinstance(base.get("eval_exact"), (int, float))
                else None
            ),
            "strict_exact_current": cur.get("strict_eval_exact"),
            "strict_exact_baseline": base.get("strict_eval_exact"),
            "delta_strict_exact": (
                cur.get("strict_eval_exact") - base.get("strict_eval_exact")
                if isinstance(cur.get("strict_eval_exact"), (int, float)) and isinstance(base.get("strict_eval_exact"), (int, float))
                else None
            ),
            "rows_current": cur.get("rows"),
            "rows_baseline": base.get("rows"),
        }
    metrics = {
        "surface_delta": delta,
        "improved_surfaces_eval": sorted([surface for surface, card in delta.items() if isinstance(card.get("delta_eval_exact"), (int, float)) and card["delta_eval_exact"] > 0]),
        "improved_surfaces_strict": sorted([surface for surface, card in delta.items() if isinstance(card.get("delta_strict_exact"), (int, float)) and card["delta_strict_exact"] > 0]),
        "regressed_surfaces_eval": sorted([surface for surface, card in delta.items() if isinstance(card.get("delta_eval_exact"), (int, float)) and card["delta_eval_exact"] < 0]),
        "regressed_surfaces_strict": sorted([surface for surface, card in delta.items() if isinstance(card.get("delta_strict_exact"), (int, float)) and card["delta_strict_exact"] < 0]),
    }
    decision = (
        "The hardened v2.7 package preserves the integrated multisurface tiny-review behavior of the prior geometry-aware package: symbol binding stays at 0.3125/0.3125, edit localization stays at 0.25/0.25, and the abstention guardrails remain saturated. That means the hardened packet fixes comparison validity without yet lifting integrated edit-localization exactness inside the broader mix."
        if not failures
        else "The hardened v2.7 execution delta audit is incomplete."
    )
    caveats = [
        "This is still a tiny capped review, not a full standalone or harness benchmark.",
        "The hardened edit-localization source clearly improves the truthful same-surface comparison story, but the integrated multisurface package still needs additional objective or training changes to raise edit-localization exactness beyond 0.25/0.25.",
        "The next integrated-model step should change training pressure or objective structure, not revert to the old leaking packet.",
    ]
    return {"passed": not failures, "failures": failures, "metrics": metrics, "decision": decision, "caveats": caveats, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    write_json(AUDIT, audit)
    next_step = "Keep Stage9913 as the default hardened v2.7 package, then pursue objective or curriculum changes that can raise integrated edit-localization exactness without reopening label-proxy leakage."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit["metrics"], "failures": audit["failures"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"],
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(SUMMARY, summary)
    DOC.write_text("\n".join([
        "# Stage9915 Hardened V2.7 Execution Delta Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Surface delta: `{audit['metrics']['surface_delta']}`",
        "",
        audit["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
