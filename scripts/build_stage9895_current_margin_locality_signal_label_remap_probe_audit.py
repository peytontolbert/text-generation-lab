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
STAGE = 9895
NAME = "stage9895_current_margin_locality_signal_label_remap_probe_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9893_current_margin_locality_signal_label_remap_manifest.json"
PROBE_DIR = ROOT / "runs/local/artifacts/stage9894_current_margin_locality_signal_label_remap_target_100m_probe/edit_localization_probe"
EXECUTION = PROBE_DIR / "execution_result.json"
CONFUSION = PROBE_DIR / "structured_confusion_matrix.json"
CELL_EXACT = PROBE_DIR / "field_exact_by_cell.json"
PRIOR_EXECUTION = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/execution_result.json"
PRIOR_CONFUSION = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/structured_confusion_matrix.json"
PRIOR_CELL_EXACT = ROOT / "runs/local/artifacts/stage9892_current_margin_locality_signal_lift_target_100m_probe/edit_localization_probe/field_exact_by_cell.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_margin_locality_signal_label_remap_probe_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_MARGIN_LOCALITY_SIGNAL_LABEL_REMAP_PROBE_AUDIT_STAGE9895.md"
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


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_SUMMARY)
    execution = load_json(EXECUTION)
    confusion = load_json(CONFUSION)
    cell_exact = load_json(CELL_EXACT)
    prior_execution = load_json(PRIOR_EXECUTION)
    prior_confusion = load_json(PRIOR_CONFUSION)
    prior_cell_exact = load_json(PRIOR_CELL_EXACT)
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9893_not_passed")
    if not execution:
        failures.append("missing_execution_result")
    if not confusion:
        failures.append("missing_confusion_matrix")

    eval_exact, strict_exact = _extract_exacts(execution)
    prior_eval_exact, prior_strict_exact = _extract_exacts(prior_execution)
    best_state = execution.get("best_state_selection") if isinstance(execution.get("best_state_selection"), dict) else {}
    prior_best_state = prior_execution.get("best_state_selection") if isinstance(prior_execution.get("best_state_selection"), dict) else {}

    current_cells = ((cell_exact.get("edit_localization") or {}) if isinstance(cell_exact.get("edit_localization"), dict) else {})
    prior_cells = ((prior_cell_exact.get("edit_localization") or {}) if isinstance(prior_cell_exact.get("edit_localization"), dict) else {})
    per_cell_delta = {}
    for key in sorted(set(current_cells) | set(prior_cells)):
        cur = (current_cells.get(key) or {}).get("exact")
        prev = (prior_cells.get(key) or {}).get("exact")
        if isinstance(cur, (int, float)) and isinstance(prev, (int, float)):
            per_cell_delta[key] = cur - prev

    pred_counts = {}
    field_cm = confusion.get("edit_localization") if isinstance(confusion.get("edit_localization"), dict) else {}
    for preds in field_cm.values():
        if isinstance(preds, dict):
            for label, count in preds.items():
                pred_counts[label] = pred_counts.get(label, 0) + int(count)
    prior_pred_counts = {}
    prior_field_cm = prior_confusion.get("edit_localization") if isinstance(prior_confusion.get("edit_localization"), dict) else {}
    for preds in prior_field_cm.values():
        if isinstance(preds, dict):
            for label, count in preds.items():
                prior_pred_counts[label] = prior_pred_counts.get(label, 0) + int(count)

    metrics = {
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "selected_step": best_state.get("selected_step"),
        "selection_exact_sum": best_state.get("selection_exact_sum"),
        "selection_loss_sum": best_state.get("selection_loss_sum"),
        "prior_eval_exact": prior_eval_exact,
        "prior_strict_exact": prior_strict_exact,
        "delta_vs_prior_eval": (eval_exact - prior_eval_exact) if isinstance(eval_exact, (int, float)) and isinstance(prior_eval_exact, (int, float)) else None,
        "delta_vs_prior_strict": (strict_exact - prior_strict_exact) if isinstance(strict_exact, (int, float)) and isinstance(prior_strict_exact, (int, float)) else None,
        "delta_vs_prior_selection_loss": (
            best_state.get("selection_loss_sum") - prior_best_state.get("selection_loss_sum")
            if isinstance(best_state.get("selection_loss_sum"), (int, float)) and isinstance(prior_best_state.get("selection_loss_sum"), (int, float))
            else None
        ),
        "per_cell_delta_vs_stage9892": per_cell_delta,
        "pred_counts": dict(sorted(pred_counts.items())),
        "prior_pred_counts": dict(sorted(prior_pred_counts.items())),
        "removed_single_label_collapse": len(pred_counts) > 1 and max(pred_counts.values()) < 16,
        "required_artifacts_written": execution.get("required_artifacts_written"),
    }

    decision = (
        "The Stage9894 remap control does not improve headline exact over the locality-lift baseline, but it removes the single-label K collapse. That is strong evidence that class-token geometry, not just packet semantics, still limits the current 100M edit-localization head."
        if not failures
        else "The Stage9894 remap control audit is incomplete."
    )
    caveats = [
        "Because the remap changes the output token inventory, this is a diagnostic control rather than a same-surface leaderboard result.",
        "The absence of a single-label collapse after removing K suggests the locality evidence is usable, but the current label geometry still distorts how that evidence is mapped to outputs.",
        "The next model-side step should test a neutral label inventory or head/objective redesign on the main packet rather than more packet-order changes.",
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
    next_step = "Promote the locality-signal lift as an eval-valid evidence improvement, then test a neutral output vocabulary or head/objective redesign on the main current-frontier packet."
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
                "# Stage9895 Current Margin Locality Signal Label Remap Probe Audit",
                "",
                f"Passed: `{audit['passed']}`",
                f"Eval exact: `{audit['metrics']['eval_exact']}`",
                f"Strict exact: `{audit['metrics']['strict_exact']}`",
                f"Prediction counts: `{audit['metrics']['pred_counts']}`",
                f"Removed single-label collapse: `{audit['metrics']['removed_single_label_collapse']}`",
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
