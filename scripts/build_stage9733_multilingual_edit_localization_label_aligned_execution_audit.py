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
STAGE = 9733
NAME = "stage9733_multilingual_edit_localization_label_aligned_execution_audit"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage9732_multilingual_edit_localization_label_aligned_package.json"
BASELINE = ROOT / "runs/local/artifacts/stage9729_probe_smoke_edit_localization_exec/execution_result.json"
RUN_DIR = ROOT / "runs/local/artifacts/stage9733_multilingual_edit_localization_label_aligned_exec"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "multilingual_edit_localization_label_aligned_execution_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_EDIT_LOCALIZATION_LABEL_ALIGNED_EXECUTION_AUDIT_STAGE9733.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
REQUIRED = [
    "probe_contract_audit.json",
    "execution_result.json",
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "module_delta_norms.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = load_json(SOURCE_SUMMARY)
    baseline = load_json(BASELINE)
    result = load_json(RUN_DIR / "execution_result.json")
    missing = [name for name in REQUIRED if not (RUN_DIR / name).exists()]
    baseline_eval = _exact(baseline, "eval")
    baseline_strict = _exact(baseline, "strict_eval")
    eval_exact = _exact(result, "eval")
    strict_exact = _exact(result, "strict_eval")
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9732_not_passed")
    if not result:
        failures.append("missing_execution_result")
    if impl.get("probe_scale") != "target_100m":
        failures.append("not_target_100m")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        failures.append("final_checkpoint_exported")
    if result.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    if result.get("train_rows") != 28 or result.get("eval_rows") != 28 or result.get("strict_rows") != 28:
        failures.append("unexpected_row_counts")
    if missing:
        failures.append("missing_required_artifacts")
    improved = (eval_exact or 0.0) > (baseline_eval or 0.0) and (strict_exact or 0.0) > (baseline_strict or 0.0)
    audit = {
        "passed": not failures,
        "failures": failures,
        "baseline_eval_exact": baseline_eval,
        "baseline_strict_exact": baseline_strict,
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "improved_over_stage9729": improved,
        "missing_required_artifacts": missing,
        "authority": dict(AUTHORITY_CLOSED),
    }
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = "If the label-aligned package improves over the Stage9729 zero-exact baseline, extend the same label-aligned intervention to patch_operator and verifier_repair; otherwise inspect logits/confusion for deeper objective mismatch."
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), **audit},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT)), "run_dir": str(RUN_DIR.relative_to(ROOT))},
        "decision": "Audited the executed label-aligned multilingual edit-localization run against the Stage9729 zero-exact baseline.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9733 Multilingual Edit Localization Label-Aligned Execution Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Baseline eval/strict exact: `{baseline_eval}` / `{baseline_strict}`",
        f"New eval/strict exact: `{eval_exact}` / `{strict_exact}`",
        f"Improved over Stage9729: `{improved}`",
        "",
        "This stage compares the label-aligned multilingual edit-localization execution against the earlier zero-exact tiny-package baseline.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({"stage": STAGE, "passed": summary["passed"], "eval_exact": eval_exact, "strict_exact": strict_exact, "improved": improved, "failures": failures, "next_best_step": next_step}, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
