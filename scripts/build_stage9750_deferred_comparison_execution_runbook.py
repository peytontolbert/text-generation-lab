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
STAGE = 9750
NAME = "stage9750_deferred_comparison_execution_runbook"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
RUNBOOK = OUT_DIR / "deferred_comparison_execution_runbook.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DEFERRED_COMPARISON_EXECUTION_RUNBOOK_STAGE9750.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

STANDALONE_QUEUE = ROOT / "runs/local/artifacts/stage9748_supported_standalone_gemma_queue/supported_standalone_gemma_queue.json"
HARNESS_QUEUE = ROOT / "runs/local/artifacts/stage9749_full_product_harness_gemma_queue/full_product_harness_gemma_queue.json"
TRAINER = ROOT / "legacy_src/scripts/train_agentkernel_lite_encdec.py"
PATCH_MINIMALITY = ROOT / "scripts/patch_minimality_complexity_meter.py"
TRACE_OBSERVABILITY = ROOT / "scripts/traced_eval_observability.py"
SEMANTIC_VERIFIER = ROOT / "scripts/semantic_equivalence_metamorphic_verifier.py"
LOCKED_SUITE = ROOT / "scripts/golden_locked_eval_suite.py"


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


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def build_runbook() -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    standalone = load_json(STANDALONE_QUEUE)
    harness = load_json(HARNESS_QUEUE)
    trainer_text = _text(TRAINER)
    standalone_entries = standalone.get("queue_entries") if isinstance(standalone.get("queue_entries"), list) else []
    harness_entries = harness.get("queue_entries") if isinstance(harness.get("queue_entries"), list) else []

    trainer_surface = {
        "path": str(TRAINER.relative_to(ROOT)),
        "exists": TRAINER.exists(),
        "supports_target_100m_probe_execution": "--probe-scale" in trainer_text and "--execution-authorized-for-recovery-probe" in trainer_text,
        "supports_contract_only": "--contract-only" in trainer_text,
        "exposes_gemma_flag": "--gemma" in trainer_text,
        "exposes_harness_flag": "--harness" in trainer_text,
        "writes_gemma_executed_field": "gemma_executed" in trainer_text,
        "writes_harness_executed_field": "harness_executed" in trainer_text,
    }
    support_modules = {
        "patch_minimality_complexity_meter": {
            "path": str(PATCH_MINIMALITY.relative_to(ROOT)),
            "exists": PATCH_MINIMALITY.exists(),
            "callable_script": PATCH_MINIMALITY.exists(),
        },
        "traced_eval_observability": {
            "path": str(TRACE_OBSERVABILITY.relative_to(ROOT)),
            "exists": TRACE_OBSERVABILITY.exists(),
            "callable_script": TRACE_OBSERVABILITY.exists(),
        },
        "semantic_equivalence_metamorphic_verifier": {
            "path": str(SEMANTIC_VERIFIER.relative_to(ROOT)),
            "exists": SEMANTIC_VERIFIER.exists(),
            "callable_script": SEMANTIC_VERIFIER.exists(),
        },
        "golden_locked_eval_suite": {
            "path": str(LOCKED_SUITE.relative_to(ROOT)),
            "exists": LOCKED_SUITE.exists(),
            "callable_script": LOCKED_SUITE.exists(),
        },
    }
    failures: list[str] = []
    if standalone.get("passed") is not True:
        failures.append("stage9748_not_passed")
    if harness.get("passed") is not True:
        failures.append("stage9749_not_passed")
    if len(standalone_entries) != 13:
        failures.append("standalone_queue_entry_count_not_13")
    if len(harness_entries) != 36:
        failures.append("harness_queue_entry_count_not_36")
    if trainer_surface["exists"] is not True:
        failures.append("trainer_entrypoint_missing")
    if trainer_surface["supports_target_100m_probe_execution"] is not True:
        failures.append("trainer_probe_execution_surface_missing")
    if trainer_surface["exposes_gemma_flag"] is True:
        failures.append("unexpected_gemma_flag_in_trainer")
    if trainer_surface["exposes_harness_flag"] is True:
        failures.append("unexpected_harness_flag_in_trainer")
    if not all(module["exists"] for module in support_modules.values()):
        failures.append("required_support_module_missing")
    runbook = {
        "passed": not failures,
        "failures": failures,
        "runner_surfaces": {
            "target_100m_probe_trainer": trainer_surface,
            "standalone_gemma_runner_present": False,
            "full_product_harness_runner_present": False,
        },
        "support_modules": support_modules,
        "execution_fronts": {
            "standalone_same_surface_comparison": {
                "queue_path": str(STANDALONE_QUEUE.relative_to(ROOT)),
                "queue_entries": len(standalone_entries),
                "runner_status": "missing_gemma_runner_surface",
                "top_cell_key": standalone_entries[0]["cell_key"] if standalone_entries else None,
                "required_next_artifacts": [
                    "same_prompt_surface_gemma12b_outputs",
                    "expert_maintainer_rubric_scores",
                    "anti_cheat_cards",
                    "frozen_export_or_checkpoint_hash",
                ],
            },
            "full_product_harness_comparison": {
                "queue_path": str(HARNESS_QUEUE.relative_to(ROOT)),
                "queue_entries": len(harness_entries),
                "runner_status": "missing_harness_runner_surface",
                "top_cell_key": harness_entries[0]["cell_key"] if harness_entries else None,
                "required_next_artifacts": [
                    "harness_run_id",
                    "same_task_pack_as_gemma12b",
                    "tool_trace_spans",
                    "verifier_results",
                    "patch_minimality_or_abstain_scores",
                    "expert_maintainer_rubric_scores",
                    "anti_cheat_cards",
                ],
            },
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    return runbook


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    runbook = build_runbook()
    RUNBOOK.write_text(json.dumps(runbook, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Recover or authorize a concrete Gemma runner and a concrete full-product harness runner that consume the "
        "Stage9748 and Stage9749 queues, then execute the queued comparisons under the existing anti-cheat support modules."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": runbook["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "standalone_queue_entries": runbook["execution_fronts"]["standalone_same_surface_comparison"]["queue_entries"],
            "harness_queue_entries": runbook["execution_fronts"]["full_product_harness_comparison"]["queue_entries"],
            "standalone_gemma_runner_present": runbook["runner_surfaces"]["standalone_gemma_runner_present"],
            "full_product_harness_runner_present": runbook["runner_surfaces"]["full_product_harness_runner_present"],
            "target_100m_probe_trainer_exists": runbook["runner_surfaces"]["target_100m_probe_trainer"]["exists"],
            "target_100m_probe_trainer_supports_execution": runbook["runner_surfaces"]["target_100m_probe_trainer"]["supports_target_100m_probe_execution"],
            "support_modules_present": sum(1 for module in runbook["support_modules"].values() if module["exists"]),
        },
        "artifacts": {
            "runbook": str(RUNBOOK.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a deferred comparison execution runbook that distinguishes available support modules and 100M probe surfaces from the still-missing Gemma and harness runner surfaces.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9750 Deferred Comparison Execution Runbook",
        "",
        f"Passed: `{summary['passed']}`",
        f"Standalone queue entries: `{summary['metrics']['standalone_queue_entries']}`",
        f"Harness queue entries: `{summary['metrics']['harness_queue_entries']}`",
        f"Standalone Gemma runner present: `{summary['metrics']['standalone_gemma_runner_present']}`",
        f"Full harness runner present: `{summary['metrics']['full_product_harness_runner_present']}`",
        f"Target 100M probe trainer exists: `{summary['metrics']['target_100m_probe_trainer_exists']}`",
        "",
        "This stage captures the real execution boundary in the current repo: the 100M probe trainer exists, required anti-cheat support modules exist, but no concrete Gemma runner or full-product harness runner surface is currently exposed by the recovered code.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "standalone_queue_entries": summary["metrics"]["standalone_queue_entries"],
        "harness_queue_entries": summary["metrics"]["harness_queue_entries"],
        "standalone_gemma_runner_present": summary["metrics"]["standalone_gemma_runner_present"],
        "full_product_harness_runner_present": summary["metrics"]["full_product_harness_runner_present"],
        "failures": runbook["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if runbook["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
