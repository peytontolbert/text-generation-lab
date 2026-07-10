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
STAGE = 9728
NAME = "stage9728_multilingual_execution_readiness_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "multilingual_execution_readiness_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MULTILINGUAL_EXECUTION_READINESS_LEDGER_STAGE9728.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
LANGS = ["python", "rust", "c_cpp", "web_js_ts_html"]
PRELIGHT_ROWS_PER_LANGUAGE = 16
ANTI_HACK = ROOT / "runs/summaries/stage9717_locked_multilingual_eval_hacking_audit.json"
SYMBOL_BINDING = ROOT / "runs/summaries/stage9698_symbol_binding_target_100m_structured_tiny_probe_audit.json"
SURFACES = {
    "verifier_repair": {
        "surface_label": "verifier_failure_repair_or_abstain",
        "summary": ROOT / "runs/summaries/stage9723_multilingual_verifier_repair_target100m_contract_preflight.json",
        "loss": "verifier_repair_ce",
        "package_stage": 9722,
        "preflight_stage": 9723,
    },
    "edit_localization": {
        "surface_label": "edit_localization",
        "summary": ROOT / "runs/summaries/stage9725_multilingual_edit_localization_target100m_contract_preflight.json",
        "loss": "edit_localization_ce",
        "package_stage": 9724,
        "preflight_stage": 9725,
    },
    "patch_operator": {
        "surface_label": "patch_operator_selection",
        "summary": ROOT / "runs/summaries/stage9727_multilingual_patch_operator_target100m_contract_preflight.json",
        "loss": "patch_operator_ce",
        "package_stage": 9726,
        "preflight_stage": 9727,
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


def build_multilingual_surface_records(anti_hack_summary: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for surface_key, config in SURFACES.items():
        summary = load_json(config["summary"])
        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        losses = metrics.get("loss_counts") if isinstance(metrics.get("loss_counts"), dict) else {}
        for language in LANGS:
            records.append({
                "cell_key": f"standalone_100m_weights::{language}::{surface_key}",
                "mode": "standalone_100m_weights",
                "language_family": language,
                "surface": surface_key,
                "surface_label": config["surface_label"],
                "status": "contract_only_preflight_ready" if summary.get("passed") is True else "blocked",
                "status_reason": "multilingual_target100m_contract_only_preflight_passed" if summary.get("passed") is True else "preflight_failed",
                "preflight_rows_for_language": PRELIGHT_ROWS_PER_LANGUAGE if summary.get("passed") is True else 0,
                "target_loss": config["loss"],
                "loss_count_total": losses.get(config["loss"], 0),
                "anti_hacking_gate_stage": 9717,
                "anti_hacking_gate_passed": anti_hack_summary.get("passed") is True,
                "evidence": [
                    {
                        "kind": "target_100m_contract_only_preflight",
                        "stage": config["preflight_stage"],
                        "path": str(config["summary"].relative_to(ROOT)),
                    }
                ],
                "claim_ready": False,
                "blockers": [
                    "explicit_model_execution_not_recorded",
                    "same_surface_gemma12b_comparison_missing",
                    "expert_maintainer_rubric_scores_missing",
                    "language_slice_scores_missing",
                    "harness_evidence_missing",
                    "anti_cheat_cell_attachment_missing",
                ],
                "authority": dict(AUTHORITY_CLOSED),
            })
    return records


def build_symbol_binding_records(
    anti_hack_summary: dict[str, Any],
    symbol_binding_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    metrics = symbol_binding_summary.get("metrics") if isinstance(symbol_binding_summary.get("metrics"), dict) else {}
    records: list[dict[str, Any]] = []
    for language in LANGS:
        if language == "python" and symbol_binding_summary.get("passed") is True:
            status = "support_probe_only"
            reason = "python_only_target100m_symbol_binding_probe_exists"
            evidence = [{
                "kind": "target_100m_structured_probe_support",
                "stage": 9698,
                "path": str(SYMBOL_BINDING.relative_to(ROOT)),
                "details": {
                    "eval_symbol_binding_exact": metrics.get("eval_symbol_binding_exact"),
                    "strict_symbol_binding_exact": metrics.get("strict_symbol_binding_exact"),
                    "quality_passed": symbol_binding_summary.get("quality_passed") is True,
                },
            }]
            blockers = [
                "quality_probe_not_acceptance_passing",
                "same_surface_gemma12b_comparison_missing",
                "expert_maintainer_rubric_scores_missing",
                "language_slice_scores_missing",
                "harness_evidence_missing",
                "anti_cheat_cell_attachment_missing",
            ]
        else:
            status = "missing_100m_surface_evidence"
            reason = "no_executed_symbol_binding_support_for_language"
            evidence = []
            blockers = [
                "language_specific_100m_symbol_binding_probe_missing",
                "same_surface_gemma12b_comparison_missing",
                "expert_maintainer_rubric_scores_missing",
                "language_slice_scores_missing",
                "harness_evidence_missing",
                "anti_cheat_cell_attachment_missing",
            ]
        records.append({
            "cell_key": f"standalone_100m_weights::{language}::symbol_binding",
            "mode": "standalone_100m_weights",
            "language_family": language,
            "surface": "symbol_binding",
            "surface_label": "symbol_binding",
            "status": status,
            "status_reason": reason,
            "preflight_rows_for_language": 0,
            "target_loss": "symbol_binding_ce",
            "loss_count_total": 0,
            "anti_hacking_gate_stage": 9717,
            "anti_hacking_gate_passed": anti_hack_summary.get("passed") is True,
            "evidence": evidence,
            "claim_ready": False,
            "blockers": blockers,
            "authority": dict(AUTHORITY_CLOSED),
        })
    return records


def build_ledger(anti_hack_summary: dict[str, Any], symbol_binding_summary: dict[str, Any]) -> dict[str, Any]:
    records = build_multilingual_surface_records(anti_hack_summary) + build_symbol_binding_records(anti_hack_summary, symbol_binding_summary)
    status_counts = Counter(str(record.get("status") or "unknown") for record in records)
    language_counts = Counter(str(record.get("language_family") or "") for record in records)
    surface_counts = Counter(str(record.get("surface") or "") for record in records)
    failures: list[str] = []
    if anti_hack_summary.get("passed") is not True:
        failures.append("stage9717_not_passed")
    if len(records) != 16:
        failures.append("ledger_record_count_mismatch")
    if status_counts.get("contract_only_preflight_ready") != 12:
        failures.append("expected_twelve_contract_ready_cells")
    if status_counts.get("support_probe_only") != 1:
        failures.append("expected_one_support_probe_only_cell")
    if status_counts.get("missing_100m_surface_evidence") != 3:
        failures.append("expected_three_missing_symbol_binding_cells")
    return {
        "passed": not failures,
        "failures": failures,
        "records": records,
        "metrics": {
            "records": len(records),
            "status_counts": dict(sorted(status_counts.items())),
            "language_counts": dict(sorted(language_counts.items())),
            "surface_counts": dict(sorted(surface_counts.items())),
            "claim_ready_cells": 0,
            "contract_only_preflight_ready_cells": status_counts.get("contract_only_preflight_ready", 0),
            "support_probe_only_cells": status_counts.get("support_probe_only", 0),
            "missing_100m_surface_evidence_cells": status_counts.get("missing_100m_surface_evidence", 0),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    anti_hack_summary = load_json(ANTI_HACK)
    symbol_binding_summary = load_json(SYMBOL_BINDING)
    ledger = build_ledger(anti_hack_summary, symbol_binding_summary)
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use Stage9728 as the single execution gate: run explicit multilingual target-100M structured probes for "
        "verifier_repair, edit_localization, and patch_operator across python/rust/c_cpp/web_js_ts_html, extend "
        "symbol_binding beyond python, then attach same-surface Gemma-12B, harness, expert-maintainer, and anti-cheat evidence."
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
        "decision": "Aggregated multilingual target-100M execution-readiness evidence across current structured surfaces without opening any training or comparison claim.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9728 Multilingual Execution Readiness Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Records: `{summary['metrics']['records']}`",
        f"Contract-only preflight-ready cells: `{summary['metrics']['contract_only_preflight_ready_cells']}`",
        f"Support-probe-only cells: `{summary['metrics']['support_probe_only_cells']}`",
        f"Missing 100M surface evidence cells: `{summary['metrics']['missing_100m_surface_evidence_cells']}`",
        "",
        "This stage collapses the current multilingual 100M readiness state into one ledger. Three structured surfaces are contract-only preflight-ready across python, rust, c_cpp, and web_js_ts_html; symbol binding remains Python-only support evidence and is still missing equivalent evidence for the other languages.",
        "",
        "No record is claim-ready. Gemma-12B comparisons, explicit multilingual 100M execution, harness evidence, expert-maintainer rubric scores, and cell-specific anti-cheat attachments are still missing.",
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
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if ledger["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
