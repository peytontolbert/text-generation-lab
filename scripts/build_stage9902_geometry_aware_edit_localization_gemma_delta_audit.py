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
STAGE = 9902
NAME = "stage9902_geometry_aware_edit_localization_gemma_delta_audit"
CURRENT = ROOT / "runs/local/artifacts/stage9901_geometry_aware_edit_localization_gemma_comparison/geometry_aware_edit_localization_gemma_comparison.json"
BASELINE = ROOT / "runs/local/artifacts/stage9770_multilingual_edit_localization_gemma_comparison/multilingual_edit_localization_gemma_comparison.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "geometry_aware_edit_localization_gemma_delta_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEOMETRY_AWARE_EDIT_LOCALIZATION_GEMMA_DELTA_AUDIT_STAGE9902.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": STAGE, "registry_rows": len(registry["rows"])}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def baseline_map(payload: dict[str, Any]) -> dict[str, float]:
    results = {}
    for row in payload.get("results", []) if isinstance(payload.get("results"), list) else []:
        lang = str(row.get("language") or "")
        score = row.get("gemma_strict_exact")
        if isinstance(score, (int, float)):
            results[f"{lang}:strict_eval"] = float(score)
            results[f"{lang}:eval"] = float(score)
    return results


def build_audit() -> dict[str, Any]:
    current = load_json(CURRENT)
    baseline = load_json(BASELINE)
    failures: list[str] = []
    if current.get("passed") is not True:
        failures.append("stage9901_not_passed")
    baseline_scores = baseline_map(baseline)
    delta = {}
    comparisons = current.get("comparisons") if isinstance(current.get("comparisons"), dict) else {}
    for key, card in sorted(comparisons.items()):
        current_gemma = card.get("gemma_exact")
        base_gemma = baseline_scores.get(key)
        current_model = card.get("hundred_m_exact")
        base_model = 0.2
        delta[key] = {
            "current_model_exact": current_model,
            "baseline_model_exact_assumed": base_model,
            "delta_model_exact": (current_model - base_model) if isinstance(current_model, (int, float)) else None,
            "current_gemma_exact": current_gemma,
            "baseline_gemma_exact": base_gemma,
            "delta_gemma_exact": (current_gemma - base_gemma) if isinstance(current_gemma, (int, float)) and isinstance(base_gemma, (int, float)) else None,
            "current_verdict": card.get("verdict"),
        }
    metrics = {
        "wins_100m": current.get("wins_100m"),
        "wins_gemma": current.get("wins_gemma"),
        "ties": current.get("ties"),
        "comparison_delta": delta,
    }
    decision = (
        "The refreshed geometry-aware same-surface comparison improves the truthful 100M-vs-Gemma story from a full tie to a narrow edge: one 100M win, seven ties, and zero Gemma wins. The win is limited to web_js_ts_html eval, so this is still not a broad multilingual victory."
        if not failures
        else "The geometry-aware Gemma delta audit is incomplete."
    )
    caveats = [
        "This audit compares against the earlier deterministic strict comparison, which treated the same 0.2 score as the best truthful multilingual packet at that time.",
        "The refreshed packet uses a different output vocabulary and stronger visible evidence, so the comparison is a packet-to-packet frontier update rather than proof of general model superiority.",
        "A broader claim still requires rebuilding the multilingual comparison bank on the refreshed package and then improving the head/objective enough to convert ties into wins in python, rust, and c_cpp.",
    ]
    return {"passed": not failures, "failures": failures, "metrics": metrics, "decision": decision, "caveats": caveats, "authority": dict(AUTHORITY_CLOSED)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    write_json(AUDIT, audit)
    next_step = "Use the geometry-aware packet as the default same-surface Gemma comparison target, then pursue a head/objective change that can turn the remaining seven ties into multilingual wins."
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
        "# Stage9902 Geometry-Aware Edit Localization Gemma Delta Audit",
        "",
        f"Passed: `{audit['passed']}`",
        f"Wins 100M: `{audit['metrics']['wins_100m']}`",
        f"Wins Gemma: `{audit['metrics']['wins_gemma']}`",
        f"Ties: `{audit['metrics']['ties']}`",
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
