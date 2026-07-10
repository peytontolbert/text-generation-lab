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
STAGE = 9905
NAME = "stage9905_current_margin_locality_signal_neutral_label_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9903_current_margin_locality_signal_neutral_label_manifest.json"
PROBE_DIR = ROOT / "runs/local/artifacts/stage9904_current_margin_locality_signal_neutral_label_target_100m_probe/edit_localization_probe"
EXECUTION = PROBE_DIR / "execution_result.json"
WRAPPER_AUDIT = ROOT / "runs/local/artifacts/stage9904_current_margin_locality_signal_neutral_label_target_100m_probe/current_margin_locality_signal_neutral_label_target_100m_probe_audit.json"
BEST_STATE = PROBE_DIR / "best_structured_state_selection.json"
CONFUSION = PROBE_DIR / "structured_confusion_matrix.json"
CELL_EXACT = PROBE_DIR / "field_exact_by_cell.json"
PRIOR_EXECUTION = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/execution_result.json"
PRIOR_CONFUSION = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/structured_confusion_matrix.json"
PRIOR_CELL_EXACT = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/field_exact_by_cell.json"
REMAP_EXECUTION = ROOT / "runs/local/artifacts/stage9894_current_margin_locality_signal_label_remap_target_100m_probe/edit_localization_probe/execution_result.json"
REMAP_CONFUSION = ROOT / "runs/local/artifacts/stage9894_current_margin_locality_signal_label_remap_target_100m_probe/edit_localization_probe/structured_confusion_matrix.json"
REMAP_CELL_EXACT = ROOT / "runs/local/artifacts/stage9894_current_margin_locality_signal_label_remap_target_100m_probe/edit_localization_probe/field_exact_by_cell.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_locality_signal_neutral_label_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_LOCALITY_SIGNAL_NEUTRAL_LABEL_PROBE_AUDIT_STAGE9905.md"
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


def _extract_exacts(execution: dict[str, Any]) -> tuple[Any, Any]:
    eval_exact = (((execution.get("eval") or {}).get("eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    strict_exact = (((execution.get("eval") or {}).get("strict_eval") or {}).get("field_exact") or {}).get("edit_localization", {}).get("exact")
    return eval_exact, strict_exact


def _pred_counts(confusion: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    field_cm = confusion.get("edit_localization") if isinstance(confusion.get("edit_localization"), dict) else {}
    for preds in field_cm.values():
        if isinstance(preds, dict):
            for label, count in preds.items():
                counts[label] = counts.get(label, 0) + int(count)
    return dict(sorted(counts.items()))


def _load_execution_with_fallback() -> dict[str, Any]:
    execution = load_json(EXECUTION)
    if execution:
        return execution
    wrapper = load_json(WRAPPER_AUDIT)
    best_state = load_json(BEST_STATE)
    if not wrapper:
        return {}
    return {
        "runtime_executed": wrapper.get("runtime_executed"),
        "required_artifacts_written": wrapper.get("required_row_artifacts_present"),
        "eval": wrapper.get("eval") or {},
        "best_state_selection": best_state if isinstance(best_state, dict) else {},
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    execution = _load_execution_with_fallback()
    confusion = load_json(CONFUSION)
    cell_exact = load_json(CELL_EXACT)
    prior_execution = load_json(PRIOR_EXECUTION)
    prior_confusion = load_json(PRIOR_CONFUSION)
    prior_cell_exact = load_json(PRIOR_CELL_EXACT)
    remap_execution = load_json(REMAP_EXECUTION)
    remap_confusion = load_json(REMAP_CONFUSION)
    remap_cell_exact = load_json(REMAP_CELL_EXACT)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9903_not_passed")
    if not execution:
        failures.append("missing_execution_result")
    if not confusion:
        failures.append("missing_confusion_matrix")

    eval_exact, strict_exact = _extract_exacts(execution)
    prior_eval_exact, prior_strict_exact = _extract_exacts(prior_execution)
    remap_eval_exact, remap_strict_exact = _extract_exacts(remap_execution)
    best_state = execution.get("best_state_selection") if isinstance(execution.get("best_state_selection"), dict) else {}
    current_cells = (cell_exact.get("edit_localization") or {}) if isinstance(cell_exact.get("edit_localization"), dict) else {}
    prior_cells = (prior_cell_exact.get("edit_localization") or {}) if isinstance(prior_cell_exact.get("edit_localization"), dict) else {}
    remap_cells = (remap_cell_exact.get("edit_localization") or {}) if isinstance(remap_cell_exact.get("edit_localization"), dict) else {}
    per_cell_delta_vs_9892 = {}
    per_cell_delta_vs_9894 = {}
    for key in sorted(set(current_cells) | set(prior_cells) | set(remap_cells)):
        cur = (current_cells.get(key) or {}).get("exact")
        prev = (prior_cells.get(key) or {}).get("exact")
        remap = (remap_cells.get(key) or {}).get("exact")
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            per_cell_delta_vs_9892[key] = cur - prev
        if isinstance(cur, (int, float)) and isinstance(remap, (int, float)):
            per_cell_delta_vs_9894[key] = cur - remap

    pred_counts = _pred_counts(confusion)
    prior_pred_counts = _pred_counts(prior_confusion)
    remap_pred_counts = _pred_counts(remap_confusion)
    metrics = {
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "selected_step": best_state.get("selected_step"),
        "selection_exact_sum": best_state.get("selection_exact_sum"),
        "selection_loss_sum": best_state.get("selection_loss_sum"),
        "prior_eval_exact": prior_eval_exact,
        "prior_strict_exact": prior_strict_exact,
        "remap_eval_exact": remap_eval_exact,
        "remap_strict_exact": remap_strict_exact,
        "delta_vs_stage9892_eval": (eval_exact - prior_eval_exact) if isinstance(eval_exact, (int, float)) and isinstance(prior_eval_exact, (int, float)) else None,
        "delta_vs_stage9892_strict": (strict_exact - prior_strict_exact) if isinstance(strict_exact, (int, float)) and isinstance(prior_strict_exact, (int, float)) else None,
        "delta_vs_stage9894_eval": (eval_exact - remap_eval_exact) if isinstance(eval_exact, (int, float)) and isinstance(remap_eval_exact, (int, float)) else None,
        "delta_vs_stage9894_strict": (strict_exact - remap_strict_exact) if isinstance(strict_exact, (int, float)) and isinstance(remap_strict_exact, (int, float)) else None,
        "per_cell_delta_vs_stage9892": per_cell_delta_vs_9892,
        "per_cell_delta_vs_stage9894": per_cell_delta_vs_9894,
        "pred_counts": pred_counts,
        "prior_pred_counts": prior_pred_counts,
        "remap_pred_counts": remap_pred_counts,
        "uses_all_neutral_labels": sorted(pred_counts) == ["A", "B", "C", "D"],
        "required_artifacts_written": execution.get("required_artifacts_written"),
    }
    if not failures and metrics["delta_vs_stage9894_strict"] and metrics["delta_vs_stage9894_strict"] > 0:
        decision = "The Stage9904 neutral-label control improves over the stage9894 label-remap control, which is evidence that output-vocabulary geometry still materially affects the current 100M edit-localization head."
    elif not failures:
        decision = "The Stage9904 neutral-label control does not materially beat the stage9894 remap control, which points away from simple label-identity effects and back toward deeper head/objective limitations."
    else:
        decision = "The Stage9904 neutral-label control audit is incomplete."
    caveats = [
        "This remains a diagnostic control rather than a same-surface leaderboard packet because the output vocabulary is intentionally changed.",
        "Any exact lift here should be treated as evidence about label geometry and head behavior, not as a broad software-maintenance capability gain.",
        "The next comparator move should only upgrade the main packet if the neutral-label control yields a stable exact lift and preserves row-level evidence validity.",
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
    next_step = "If the neutral-label control is better than stages 9892 and 9894, run the same neutral vocabulary through a same-surface Gemma comparison; otherwise keep the packet fixed and change the head/objective rather than the labels."
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
                "# Stage9905 Current Margin Locality Signal Neutral Label Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Eval exact: `{audit['metrics']['eval_exact']}`",
                f"Strict exact: `{audit['metrics']['strict_exact']}`",
                f"Prediction counts: `{audit['metrics']['pred_counts']}`",
                f"Uses all neutral labels: `{audit['metrics']['uses_all_neutral_labels']}`",
                "",
                audit["decision"],
                "",
                f"Next: {next_step}",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": audit["passed"], "metrics": audit["metrics"], "failures": audit["failures"]}, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
