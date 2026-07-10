#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9729
NAME = "stage9729_multilingual_structured_execution_support_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "multilingual_structured_execution_support_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_STRUCTURED_EXECUTION_SUPPORT_LEDGER_STAGE9729.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_LEDGER = ROOT / "runs/summaries/stage9728_multilingual_execution_readiness_ledger.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
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
SURFACES = {
    "verifier_repair": {
        "surface_label": "verifier_failure_repair_or_abstain",
        "run_dir": ROOT / "runs/local/artifacts/stage9729_probe_smoke_verifier_repair_exec",
        "field": "verifier_repair",
        "loss": "verifier_repair_ce",
    },
    "edit_localization": {
        "surface_label": "edit_localization",
        "run_dir": ROOT / "runs/local/artifacts/stage9729_probe_smoke_edit_localization_exec",
        "field": "edit_localization",
        "loss": "edit_localization_ce",
    },
    "patch_operator": {
        "surface_label": "patch_operator_selection",
        "run_dir": ROOT / "runs/local/artifacts/stage9729_probe_smoke_patch_operator_exec",
        "field": "patch_operator",
        "loss": "patch_operator_ce",
    },
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _split_field_exact(execution_result: dict[str, Any], split: str, field: str) -> float | None:
    eval_card = execution_result.get("eval") if isinstance(execution_result.get("eval"), dict) else {}
    split_card = eval_card.get(split) if isinstance(eval_card.get(split), dict) else {}
    field_card = split_card.get("field_exact") if isinstance(split_card.get("field_exact"), dict) else {}
    metrics = field_card.get(field) if isinstance(field_card.get(field), dict) else {}
    value = metrics.get("exact")
    return None if value is None else float(value)


def audit_surface(surface: str, config: dict[str, Any]) -> dict[str, Any]:
    run_dir = config["run_dir"]
    contract = load_json(run_dir / "probe_contract_audit.json")
    result = load_json(run_dir / "execution_result.json")
    module_delta = load_json(run_dir / "module_delta_norms.json")
    missing = [name for name in REQUIRED if not (run_dir / name).exists()]
    impl = result.get("implementation") if isinstance(result.get("implementation"), dict) else {}
    loss_counts = contract.get("loss_counts") if isinstance(contract.get("loss_counts"), dict) else {}
    expected_field = str(config["field"])
    eval_exact = _split_field_exact(result, "eval", expected_field)
    strict_exact = _split_field_exact(result, "strict_eval", expected_field)
    failures: list[str] = []
    if contract.get("passed") is not True:
        failures.append("contract_not_passed")
    if result.get("mode") is None:
        failures.append("missing_execution_result")
    if impl.get("probe_scale") != "target_100m":
        failures.append("not_target_100m")
    if result.get("runtime_executed") or result.get("gemma_executed") or result.get("harness_executed"):
        failures.append("forbidden_external_execution")
    if result.get("final_checkpoint_exported"):
        failures.append("final_checkpoint_exported")
    if result.get("required_artifacts_written") is not True:
        failures.append("required_artifacts_not_written")
    if result.get("fields") != [expected_field]:
        failures.append("unexpected_fields")
    if result.get("train_rows") != 32 or result.get("eval_rows") != 16 or result.get("strict_rows") != 16:
        failures.append("unexpected_row_caps")
    if loss_counts.get(config["loss"]) != 64:
        failures.append("expected_loss_count_not_64")
    forbidden = {key: value for key, value in loss_counts.items() if key != config["loss"] and value}
    if forbidden:
        failures.append("forbidden_loss_counts_nonzero")
    if float(module_delta.get("decoder_delta_norm") or 0.0) != 0.0:
        failures.append("decoder_delta_nonzero")
    if result.get("structured_optimizer_isolated") is not True:
        failures.append("structured_optimizer_not_isolated")
    if missing:
        failures.append("missing_required_artifacts")
    return {
        "surface": surface,
        "surface_label": config["surface_label"],
        "passed": not failures,
        "failures": failures,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "field": expected_field,
        "eval_exact": eval_exact,
        "strict_exact": strict_exact,
        "loss_counts": loss_counts,
        "estimated_parameter_count": impl.get("estimated_parameter_count"),
        "structured_optimizer_isolated": result.get("structured_optimizer_isolated") is True,
        "runtime_executed": result.get("runtime_executed") is True,
        "gemma_executed": result.get("gemma_executed") is True,
        "harness_executed": result.get("harness_executed") is True,
        "final_checkpoint_exported": result.get("final_checkpoint_exported") is True,
        "missing_required_artifacts": missing,
    }


def build_ledger() -> dict[str, Any]:
    source = load_json(SOURCE_LEDGER)
    records: list[dict[str, Any]] = []
    surface_audits = {surface: audit_surface(surface, config) for surface, config in SURFACES.items()}
    failures: list[str] = []
    if source.get("passed") is not True:
        failures.append("stage9728_not_passed")
    for surface, audit in surface_audits.items():
        if not audit["passed"]:
            failures.append(f"surface_execution_audit_failed:{surface}")
        for language in LANGS:
            records.append({
                "cell_key": f"standalone_100m_weights::{language}::{surface}",
                "mode": "standalone_100m_weights",
                "language_family": language,
                "surface": surface,
                "surface_label": audit["surface_label"],
                "status": "executed_supporting_evidence" if audit["passed"] else "executed_evidence_failed",
                "status_reason": "multilingual_target100m_execution_completed" if audit["passed"] else "surface_execution_audit_failed",
                "surface_eval_exact": audit["eval_exact"],
                "surface_strict_exact": audit["strict_exact"],
                "claim_ready": False,
                "evidence": [
                    {
                        "kind": "target_100m_structured_execution_support",
                        "stage": STAGE,
                        "run_dir": audit["run_dir"],
                        "field": audit["field"],
                        "surface_eval_exact": audit["eval_exact"],
                        "surface_strict_exact": audit["strict_exact"],
                    }
                ],
                "blockers": [
                    "language_slice_scores_not_separated_within_surface_run",
                    "same_surface_gemma12b_comparison_missing",
                    "expert_maintainer_rubric_scores_missing",
                    "harness_evidence_missing",
                    "anti_cheat_cell_attachment_missing",
                ],
                "authority": dict(AUTHORITY_CLOSED),
            })
    status_counts = Counter(str(record.get("status") or "unknown") for record in records)
    if len(records) != 12:
        failures.append("ledger_record_count_mismatch")
    if status_counts.get("executed_supporting_evidence") != 12:
        failures.append("expected_twelve_executed_supporting_cells")
    return {
        "passed": not failures,
        "failures": failures,
        "surface_audits": surface_audits,
        "records": records,
        "metrics": {
            "records": len(records),
            "status_counts": dict(sorted(status_counts.items())),
            "surface_eval_exact": {surface: audit["eval_exact"] for surface, audit in sorted(surface_audits.items())},
            "surface_strict_exact": {surface: audit["strict_exact"] for surface, audit in sorted(surface_audits.items())},
            "claim_ready_cells": 0,
            "executed_supporting_evidence_cells": status_counts.get("executed_supporting_evidence", 0),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    ledger = build_ledger()
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Split the executed multilingual surfaces by language-family scoring, extend symbol_binding execution beyond python, "
        "then attach same-surface Gemma-12B, harness, expert-maintainer, and anti-cheat evidence before making any beat-Gemma claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": ledger["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **(ledger.get("metrics") or {}),
        },
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Recorded real multilingual target-100M structured executions for verifier-repair, edit-localization, and patch-operator as supporting evidence without opening any comparison claim.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9729 Multilingual Structured Execution Support Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Records: `{summary['metrics']['records']}`",
        f"Executed supporting evidence cells: `{summary['metrics']['executed_supporting_evidence_cells']}`",
        f"Surface eval exact: `{summary['metrics']['surface_eval_exact']}`",
        f"Surface strict exact: `{summary['metrics']['surface_strict_exact']}`",
        "",
        "This stage records real target-100M multilingual structured executions for verifier_repair, edit_localization, and patch_operator. The runs stayed within the structured-only safety envelope: no runtime, Gemma, harness, checkpoint export, or decoder/denoise execution opened.",
        "",
        "These executions are supporting evidence only. They are not language-sliced comparison scores and they are not enough to claim the 100M model beats Gemma-12B.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "failures": ledger["failures"],
        "records": summary["metrics"]["records"],
        "status_counts": summary["metrics"]["status_counts"],
        "surface_eval_exact": summary["metrics"]["surface_eval_exact"],
        "surface_strict_exact": summary["metrics"]["surface_strict_exact"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if ledger["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
