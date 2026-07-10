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
STAGE = 9741
NAME = "stage9741_label_aligned_multilingual_structured_surface_comparison"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
COMPARISON = OUT_DIR / "label_aligned_multilingual_structured_surface_comparison.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LABEL_ALIGNED_MULTILINGUAL_STRUCTURED_SURFACE_COMPARISON_STAGE9741.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCES = {
    "verifier_repair": ROOT / "runs/summaries/stage9739_multilingual_verifier_repair_label_aligned_execution_audit.json",
    "edit_localization": ROOT / "runs/summaries/stage9733_multilingual_edit_localization_label_aligned_execution_audit.json",
    "patch_operator": ROOT / "runs/summaries/stage9736_multilingual_patch_operator_label_aligned_execution_audit.json",
}


def load_json(path: Path) -> Any:
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
    surface_metrics = {}
    failures: list[str] = []
    for surface, path in SOURCES.items():
        summary = load_json(path)
        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        if summary.get("passed") is not True:
            failures.append(f"{surface}_summary_not_passed")
        surface_metrics[surface] = {
            "eval_exact": metrics.get("eval_exact"),
            "strict_exact": metrics.get("strict_exact"),
            "baseline_eval_exact": metrics.get("baseline_eval_exact"),
            "baseline_strict_exact": metrics.get("baseline_strict_exact"),
            "improved_over_stage9729": metrics.get("improved_over_stage9729"),
        }
    ranked = sorted(
        surface_metrics.items(),
        key=lambda item: (
            float(item[1].get("eval_exact") or -1.0),
            float(item[1].get("strict_exact") or -1.0),
        ),
        reverse=True,
    )
    best_surface = ranked[0][0] if ranked else None
    comparison = {
        "passed": not failures,
        "failures": failures,
        "surface_metrics": surface_metrics,
        "ranking": [name for name, _ in ranked],
        "best_surface": best_surface,
        "authority": dict(AUTHORITY_CLOSED),
    }
    COMPARISON.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Use the ranked label-aligned structured surfaces to decide which 100M path is strongest enough to package for later same-surface Gemma comparison, while extending the same repair pattern to any remaining weak surfaces."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": comparison["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "best_surface": best_surface,
            "ranking": comparison["ranking"],
            "surface_metrics": surface_metrics,
        },
        "artifacts": {"comparison": str(COMPARISON.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": "Compared the three label-aligned multilingual structured surfaces after execution to identify the strongest current 100M-side path.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9741 Label-Aligned Multilingual Structured Surface Comparison",
        "",
        f"Passed: `{summary['passed']}`",
        f"Best surface: `{best_surface}`",
        f"Ranking: `{comparison['ranking']}`",
        f"Surface metrics: `{surface_metrics}`",
        "",
        "This stage compares the current executed 100M performance of the three label-aligned multilingual structured surfaces. It is still not a Gemma comparison.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "best_surface": best_surface, "ranking": comparison["ranking"], "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
