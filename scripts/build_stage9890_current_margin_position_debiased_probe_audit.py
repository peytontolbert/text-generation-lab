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
STAGE = 9890
NAME = "stage9890_current_margin_position_debiased_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9888_current_margin_position_bias_diagnostics.json"
PROBE_DIR = ROOT / "runs/local/artifacts/stage9889_current_margin_position_debiased_target_100m_probe/edit_localization_probe"
EXECUTION = PROBE_DIR / "execution_result.json"
CONFUSION = PROBE_DIR / "structured_confusion_matrix.json"
CELL_EXACT = PROBE_DIR / "field_exact_by_cell.json"
PRIOR_EXECUTION = ROOT / "runs/local/artifacts/stage9886_current_margin_hybrid_counterfactual_target_100m_probe/edit_localization_probe/execution_result.json"
PRIOR_CONFUSION = ROOT / "runs/local/artifacts/stage9886_current_margin_hybrid_counterfactual_target_100m_probe/edit_localization_probe/structured_confusion_matrix.json"
PRIOR_CELL_EXACT = ROOT / "runs/local/artifacts/stage9886_current_margin_hybrid_counterfactual_target_100m_probe/edit_localization_probe/field_exact_by_cell.json"
BROADER = ROOT / "runs/summaries/stage9877_margin_objective_schedule_aware_structured_review.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_position_debiased_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_POSITION_DEBIASED_PROBE_AUDIT_STAGE9890.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _extract_exacts(execution: dict[str, Any]) -> tuple[Any, Any]:
    eval_exact = (((execution.get("eval") or {}).get("eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    strict_exact = (((execution.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    return eval_exact, strict_exact


def _dominant_targets(confusion: dict[str, Any]) -> dict[str, str]:
    dominant: dict[str, str] = {}
    field_cm = confusion.get("edit_localization") if isinstance(confusion.get("edit_localization"), dict) else {}
    for gold, preds in field_cm.items():
        if not isinstance(preds, dict) or not preds:
            continue
        dominant[str(gold)] = max(preds.items(), key=lambda item: item[1])[0]
    return dominant


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    execution = load_json(EXECUTION)
    confusion = load_json(CONFUSION)
    cell_exact = load_json(CELL_EXACT)
    prior_execution = load_json(PRIOR_EXECUTION)
    prior_confusion = load_json(PRIOR_CONFUSION)
    prior_cell_exact = load_json(PRIOR_CELL_EXACT)
    broader = _broader_edit_metrics(load_json(BROADER))
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9888_not_passed")
    if not execution:
        failures.append("missing_execution_result")
    if not confusion:
        failures.append("missing_confusion_matrix")
    if not cell_exact:
        failures.append("missing_cell_exact")

    eval_exact, strict_exact = _extract_exacts(execution)
    prior_eval_exact, prior_strict_exact = _extract_exacts(prior_execution)
    best_state = execution.get("best_state_selection") if isinstance(execution.get("best_state_selection"), dict) else {}
    prior_best_state = prior_execution.get("best_state_selection") if isinstance(prior_execution.get("best_state_selection"), dict) else {}
    broader_eval = broader.get("eval_exact")
    broader_strict = broader.get("strict_eval_exact")

    current_cells = ((cell_exact.get("edit_localization") or {}) if isinstance(cell_exact.get("edit_localization"), dict) else {})
    prior_cells = ((prior_cell_exact.get("edit_localization") or {}) if isinstance(prior_cell_exact.get("edit_localization"), dict) else {})
    per_cell_delta = {}
    for key in sorted(set(current_cells) | set(prior_cells)):
        cur = (current_cells.get(key) or {}).get("exact")
        prev = (prior_cells.get(key) or {}).get("exact")
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            per_cell_delta[key] = cur - prev

    metrics = {
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "selected_step": best_state.get("selected_step"),
        "selection_exact_sum": best_state.get("selection_exact_sum"),
        "selection_loss_sum": best_state.get("selection_loss_sum"),
        "prior_eval_exact": prior_eval_exact,
        "prior_strict_exact": prior_strict_exact,
        "prior_selection_loss_sum": prior_best_state.get("selection_loss_sum"),
        "delta_vs_prior_eval": (eval_exact - prior_eval_exact) if isinstance(eval_exact, (int, float)) and isinstance(prior_eval_exact, (int, float)) else None,
        "delta_vs_prior_strict": (strict_exact - prior_strict_exact) if isinstance(strict_exact, (int, float)) and isinstance(prior_strict_exact, (int, float)) else None,
        "delta_vs_prior_selection_loss": (
            best_state.get("selection_loss_sum") - prior_best_state.get("selection_loss_sum")
            if isinstance(best_state.get("selection_loss_sum"), (int, float)) and isinstance(prior_best_state.get("selection_loss_sum"), (int, float))
            else None
        ),
        "broader_eval_exact_baseline": broader_eval,
        "broader_strict_exact_baseline": broader_strict,
        "delta_vs_broader_eval": (eval_exact - broader_eval) if isinstance(eval_exact, (int, float)) and isinstance(broader_eval, (int, float)) else None,
        "delta_vs_broader_strict": (strict_exact - broader_strict) if isinstance(strict_exact, (int, float)) and isinstance(broader_strict, (int, float)) else None,
        "dominant_confusion_targets": _dominant_targets(confusion),
        "confusion_identical_to_stage9886": confusion == prior_confusion,
        "per_cell_delta_vs_stage9886": per_cell_delta,
        "required_artifacts_written": execution.get("required_artifacts_written"),
    }

    decision = (
        "The Stage9889 position-debiased rerun is useful as an eval-validity audit, but not as a frontier improvement. Eval exact stays flat, strict exact regresses, and the K-to-R collapse survives unchanged while web weakens."
        if not failures
        else "The Stage9889 position-debiased rerun audit is incomplete."
    )
    caveats = [
        "Removing position skew is still valuable for anti-cheat hygiene, even when it does not improve the current 100M model.",
        "Because K remains fully collapsed to R after debiasing, the dominant failure is not explained by option position alone.",
        "The next intervention should modify evidence or objective structure upstream of the opaque token head, not just packet serialization.",
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
    write_json(AUDIT, audit)
    next_step = "Keep the position-debiased packet as an eval-validity artifact, but move the next training intervention upstream to evidence or objective changes that directly break the persistent K-to-R collapse."
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
    DOC.write_text(
        "\n".join(
            [
                "# Stage9890 Current Margin Position-Debiased Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Eval exact: `{audit['metrics']['eval_exact']}`",
                f"Strict exact: `{audit['metrics']['strict_exact']}`",
                f"Delta vs Stage9886 eval: `{audit['metrics']['delta_vs_prior_eval']}`",
                f"Delta vs Stage9886 strict: `{audit['metrics']['delta_vs_prior_strict']}`",
                f"Per-cell delta vs Stage9886: `{audit['metrics']['per_cell_delta_vs_stage9886']}`",
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
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
