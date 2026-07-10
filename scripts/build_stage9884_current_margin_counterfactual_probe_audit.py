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
STAGE = 9884
NAME = "stage9884_current_margin_counterfactual_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9882_current_margin_counterfactual_execution_manifest.json"
PROBE_DIR = ROOT / "runs/local/artifacts/stage9883_current_margin_counterfactual_target_100m_probe/edit_localization_probe"
EXECUTION = PROBE_DIR / "execution_result.json"
CONFUSION = PROBE_DIR / "structured_confusion_matrix.json"
FRONTIER = ROOT / "runs/local/artifacts/stage9878_current_margin_multilingual_frontier_bridge/current_margin_multilingual_frontier_bridge.json"
BROADER = ROOT / "runs/summaries/stage9877_margin_objective_schedule_aware_structured_review.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_counterfactual_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_COUNTERFACTUAL_PROBE_AUDIT_STAGE9884.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _broader_edit_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("metrics", {}).get("surface_results") if isinstance(payload.get("metrics"), dict) else None
    if not isinstance(results, list):
        return {}
    for row in results:
        if str(row.get("surface") or "") == "edit_localization":
            return row
    return {}


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    execution = load_json(EXECUTION)
    confusion = load_json(CONFUSION)
    frontier = load_json(FRONTIER)
    broader = _broader_edit_metrics(load_json(BROADER))
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9882_not_passed")
    if not execution:
        failures.append("missing_execution_result")
    if not confusion:
        failures.append("missing_confusion_matrix")

    eval_exact = (((execution.get("eval") or {}).get("eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    strict_exact = (((execution.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    best_state = execution.get("best_state_selection") if isinstance(execution.get("best_state_selection"), dict) else {}
    broader_eval = broader.get("eval_exact")
    broader_strict = broader.get("strict_eval_exact")
    frontier_metrics = frontier.get("metrics") if isinstance(frontier.get("metrics"), dict) else {}

    dominant_errors: dict[str, str] = {}
    field_cm = confusion.get("edit_localization") if isinstance(confusion.get("edit_localization"), dict) else {}
    for gold, preds in field_cm.items():
        if not isinstance(preds, dict) or not preds:
            continue
        dominant_errors[str(gold)] = max(preds.items(), key=lambda item: item[1])[0]

    metrics = {
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "selected_step": best_state.get("selected_step"),
        "selection_exact_sum": best_state.get("selection_exact_sum"),
        "selection_loss_sum": best_state.get("selection_loss_sum"),
        "broader_eval_exact_baseline": broader_eval,
        "broader_strict_exact_baseline": broader_strict,
        "delta_vs_broader_eval": (eval_exact - broader_eval) if isinstance(eval_exact, (int, float)) and isinstance(broader_eval, (int, float)) else None,
        "delta_vs_broader_strict": (strict_exact - broader_strict) if isinstance(strict_exact, (int, float)) and isinstance(broader_strict, (int, float)) else None,
        "frontier_language_family_wins_100m": frontier_metrics.get("language_family_wins_100m"),
        "frontier_strict_language_wins_100m": frontier_metrics.get("strict_language_wins_100m"),
        "frontier_strict_language_ties": frontier_metrics.get("strict_language_ties"),
        "dominant_confusion_targets": dominant_errors,
        "required_artifacts_written": execution.get("required_artifacts_written"),
    }
    decision = (
        "The Stage9882 current-frontier mixed-replay rerun is executable and contract-clean, but it does not improve the frontier: eval exact matches the broader baseline while strict exact regresses."
        if not failures else
        "The Stage9882 current-frontier mixed-replay rerun is incomplete."
    )
    caveats = [
        "This rerun is on the trainer-compatible subset of the stronger counterfactual bank, not the full evidence-removed plus contradictory audit bank.",
        "The probe remains useful as a robustness signal even though it is not a promotion candidate.",
        "The confusion matrix shows substantial collapse toward R, especially for gold K, which suggests the mixed-replay rows are changing the class balance or decision boundary in an unhelpful way.",
    ]
    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "decision": decision,
        "caveats": caveats,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Do not promote the Stage9882 mixed-replay path directly. Either rebalance the strict mixed-replay labels or keep Stage9881 as a frozen audit bank while optimizing the main Stage9867/9878 training path separately."
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
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9884 Current Margin Counterfactual Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Eval exact: `{audit['metrics']['eval_exact']}`",
                f"Strict exact: `{audit['metrics']['strict_exact']}`",
                f"Delta vs broader eval: `{audit['metrics']['delta_vs_broader_eval']}`",
                f"Delta vs broader strict: `{audit['metrics']['delta_vs_broader_strict']}`",
                f"Dominant confusions: `{audit['metrics']['dominant_confusion_targets']}`",
                "",
                audit["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        ) + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit['passed'], "metrics": audit['metrics'], "failures": audit['failures']}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
