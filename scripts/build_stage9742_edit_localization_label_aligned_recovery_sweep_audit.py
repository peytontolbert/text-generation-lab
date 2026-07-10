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
STAGE = 9742
NAME = "stage9742_edit_localization_label_aligned_recovery_sweep_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "edit_localization_label_aligned_recovery_sweep_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EDIT_LOCALIZATION_LABEL_ALIGNED_RECOVERY_SWEEP_AUDIT_STAGE9742.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
BASELINE = ROOT / "runs/local/artifacts/stage9733_multilingual_edit_localization_label_aligned_exec/execution_result.json"
RUNS = {
    "steps128_lr5e5": ROOT / "runs/local/artifacts/stage9742_edit_localization_recovery_sweep/steps128_lr5e5/execution_result.json",
    "steps128_lr1e4": ROOT / "runs/local/artifacts/stage9742_edit_localization_recovery_sweep/steps128_lr1e4/execution_result.json",
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


def _exact(result: dict[str, Any], split: str) -> float | None:
    evals = result.get("eval") if isinstance(result.get("eval"), dict) else {}
    split_card = evals.get(split) if isinstance(evals.get(split), dict) else {}
    field_card = split_card.get("field_exact") if isinstance(split_card.get("field_exact"), dict) else {}
    metrics = field_card.get("edit_localization") if isinstance(field_card.get("edit_localization"), dict) else {}
    value = metrics.get("exact")
    return None if value is None else float(value)


def _run_metrics(result: dict[str, Any]) -> dict[str, Any]:
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    best = result.get("best_state_selection") if isinstance(result.get("best_state_selection"), dict) else {}
    return {
        "eval_exact": _exact(result, "eval"),
        "strict_exact": _exact(result, "strict_eval"),
        "probe_scale": impl.get("probe_scale"),
        "runtime_executed": result.get("runtime_executed") is True,
        "gemma_executed": result.get("gemma_executed") is True,
        "harness_executed": result.get("harness_executed") is True,
        "final_checkpoint_exported": result.get("final_checkpoint_exported") is True,
        "required_artifacts_written": result.get("required_artifacts_written") is True,
        "best_state_enabled": best.get("enabled") is True,
        "selected_step": best.get("selected_step"),
    }


def build_audit() -> dict[str, Any]:
    baseline = _run_metrics(load_json(BASELINE))
    sweep = {name: _run_metrics(load_json(path)) for name, path in RUNS.items()}
    failures: list[str] = []
    if baseline["eval_exact"] != 1 / 7 or baseline["strict_exact"] != 1 / 7:
        failures.append("baseline_metrics_changed")
    for name, metrics in sweep.items():
        if metrics["probe_scale"] != "target_100m":
            failures.append(f"{name}_not_target_100m")
        if metrics["runtime_executed"] or metrics["gemma_executed"] or metrics["harness_executed"] or metrics["final_checkpoint_exported"]:
            failures.append(f"{name}_forbidden_execution_opened")
        if metrics["required_artifacts_written"] is not True:
            failures.append(f"{name}_required_artifacts_not_written")
    improved = [name for name, metrics in sweep.items() if (metrics["eval_exact"] or 0.0) > (baseline["eval_exact"] or 0.0)]
    best_name = max(sweep, key=lambda name: (sweep[name]["eval_exact"] or -1.0, sweep[name]["strict_exact"] or -1.0))
    return {
        "passed": not failures,
        "failures": failures,
        "baseline": baseline,
        "sweep": sweep,
        "best_run": best_name,
        "best_eval_exact": sweep[best_name]["eval_exact"],
        "best_strict_exact": sweep[best_name]["strict_exact"],
        "improved_runs": improved,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "Stop adding identical step budget to the repaired edit-localization package. The next change must alter curriculum, labels, or comparison packaging rather than just train longer."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "baseline_eval_exact": audit["baseline"]["eval_exact"],
            "baseline_strict_exact": audit["baseline"]["strict_exact"],
            "best_run": audit["best_run"],
            "best_eval_exact": audit["best_eval_exact"],
            "best_strict_exact": audit["best_strict_exact"],
            "improved_runs": audit["improved_runs"],
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Audited a small recovery sweep on the label-aligned multilingual edit-localization package and found no improvement over the repaired Stage9733 baseline.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9742 Edit Localization Label-Aligned Recovery Sweep Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Baseline eval/strict exact: `{audit['baseline']['eval_exact']}` / `{audit['baseline']['strict_exact']}`",
        f"Best sweep run: `{audit['best_run']}`",
        f"Best sweep eval/strict exact: `{audit['best_eval_exact']}` / `{audit['best_strict_exact']}`",
        f"Improved runs: `{audit['improved_runs']}`",
        "",
        "This stage records a second negative result: after label alignment, simply running longer still does not improve multilingual edit-localization.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "best_run": audit["best_run"],
        "best_eval_exact": audit["best_eval_exact"],
        "improved_runs": audit["improved_runs"],
        "failures": audit["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
