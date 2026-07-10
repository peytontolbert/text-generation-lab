#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9751
NAME = "stage9751_expert_eval_coverage_gap_ledger"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
LEDGER = OUT_DIR / "expert_eval_coverage_gap_ledger.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPERT_EVAL_COVERAGE_GAP_LEDGER_STAGE9751.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

CONTRACT = ROOT / "runs/local/artifacts/stage9684_v27_multilingual_eval_acceptance_contract/v27_multilingual_eval_acceptance_contract.json"
ANTI_HACK = ROOT / "runs/local/artifacts/stage9717_locked_multilingual_eval_hacking_audit/locked_multilingual_eval_hacking_audit.json"
ACCEPTANCE_LEDGER = ROOT / "runs/local/artifacts/stage9718_locked_multilingual_acceptance_evidence_ledger/locked_multilingual_acceptance_evidence_ledger.json"
TRUTHFUL_SUPPORT = ROOT / "runs/local/artifacts/stage9747_truthful_standalone_acceptance_evidence_bridge/truthful_standalone_acceptance_evidence_bridge.json"
RUNBOOK = ROOT / "runs/local/artifacts/stage9750_deferred_comparison_execution_runbook/deferred_comparison_execution_runbook.json"


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


def _queue_runner_status(mode: str, runbook: dict[str, Any]) -> tuple[bool, str]:
    runners = runbook.get("runner_surfaces") if isinstance(runbook.get("runner_surfaces"), dict) else {}
    if mode == "standalone_100m_weights":
        present = runners.get("standalone_gemma_runner_present") is True
        return present, "runner_present" if present else "missing_gemma_runner_surface"
    present = runners.get("full_product_harness_runner_present") is True
    return present, "runner_present" if present else "missing_harness_runner_surface"


def build_gap_ledger(
    contract: dict[str, Any],
    anti_hack: dict[str, Any],
    acceptance_ledger: dict[str, Any],
    truthful_support: dict[str, Any],
    runbook: dict[str, Any],
) -> dict[str, Any]:
    required_skills = [str(value) for value in contract.get("maintainer_skill_areas_required") or []]
    required_languages = [str(value) for value in contract.get("languages_required") or []]
    anti_hack_records = anti_hack.get("challenge_matrix", {}).get("records") if isinstance(anti_hack.get("challenge_matrix"), dict) else []
    anti_hack_families_passed = sum(1 for row in anti_hack_records or [] if row.get("passed") is True)
    anti_hack_total_families = len(anti_hack_records or [])

    truthful_records = truthful_support.get("records") if isinstance(truthful_support.get("records"), list) else []
    truthful_index = {str(row.get("cell_key") or ""): row for row in truthful_records}

    records = acceptance_ledger.get("records") if isinstance(acceptance_ledger.get("records"), list) else []
    ledger_rows: list[dict[str, Any]] = []
    supported_skill_sets: dict[str, set[str]] = defaultdict(set)
    supported_language_counter: Counter[str] = Counter()
    supported_skill_counter: Counter[str] = Counter()
    closest_cells: list[dict[str, Any]] = []

    for record in records:
        cell_key = str(record.get("cell_key") or "")
        mode = str(record.get("mode") or "")
        language = str(record.get("language_family") or "")
        skill = str(record.get("skill_area") or "")
        missing = [str(value) for value in record.get("missing_required_evidence") or []]
        truthful = truthful_index.get(cell_key, {})
        attached = truthful.get("attached_evidence") if isinstance(truthful.get("attached_evidence"), list) else []
        has_truthful_support = bool(attached)
        runner_present, runner_gap = _queue_runner_status(mode, runbook)
        expert_rubric_attached = "expert_maintainer_rubric_scores" not in missing
        anti_cheat_cards_attached = "anti_cheat_cards" not in missing
        same_surface_comparison_attached = (
            "same_prompt_surface_gemma12b_outputs" not in missing
            if mode == "standalone_100m_weights"
            else "same_task_pack_as_gemma12b" not in missing
        )
        checkpoint_or_run_attached = (
            "frozen_export_or_checkpoint_hash" not in missing
            if mode == "standalone_100m_weights"
            else "harness_run_id" not in missing
        )
        cell = {
            "cell_key": cell_key,
            "mode": mode,
            "language_family": language,
            "skill_area": skill,
            "has_truthful_100m_support": has_truthful_support,
            "global_anti_hack_gate_passed": anti_hack.get("passed") is True,
            "cell_expert_rubric_required": True,
            "cell_expert_rubric_attached": expert_rubric_attached,
            "cell_anti_cheat_cards_required": True,
            "cell_anti_cheat_cards_attached": anti_cheat_cards_attached,
            "cross_model_comparison_attached": same_surface_comparison_attached,
            "checkpoint_or_harness_run_attached": checkpoint_or_run_attached,
            "runner_surface_present": runner_present,
            "runner_gap": runner_gap,
            "missing_required_evidence": missing,
            "claim_ready": record.get("claim_ready") is True,
        }
        ledger_rows.append(cell)
        if has_truthful_support and mode == "standalone_100m_weights":
            supported_skill_sets[language].add(skill)
            supported_language_counter[language] += 1
            supported_skill_counter[skill] += 1
            closest_cells.append({
                "cell_key": cell_key,
                "language_family": language,
                "skill_area": skill,
                "missing_required_evidence_count": len(missing),
                "missing_required_evidence": missing,
            })

    closest_cells.sort(key=lambda row: (row["missing_required_evidence_count"], row["language_family"], row["skill_area"]))
    missing_skills_by_language = {
        language: sorted(set(required_skills) - supported_skill_sets.get(language, set()))
        for language in required_languages
    }
    fully_supported_languages = sorted(language for language, skills in supported_skill_sets.items() if set(required_skills) == skills)

    metrics = {
        "records": len(ledger_rows),
        "supported_standalone_cells": sum(1 for row in ledger_rows if row["mode"] == "standalone_100m_weights" and row["has_truthful_100m_support"]),
        "cells_with_expert_rubric_attached": sum(1 for row in ledger_rows if row["cell_expert_rubric_attached"]),
        "cells_with_anti_cheat_cards_attached": sum(1 for row in ledger_rows if row["cell_anti_cheat_cards_attached"]),
        "cells_with_cross_model_comparison_attached": sum(1 for row in ledger_rows if row["cross_model_comparison_attached"]),
        "cells_with_checkpoint_or_harness_run_attached": sum(1 for row in ledger_rows if row["checkpoint_or_harness_run_attached"]),
        "supported_standalone_cells_missing_expert_rubric": sum(
            1 for row in ledger_rows
            if row["mode"] == "standalone_100m_weights" and row["has_truthful_100m_support"] and not row["cell_expert_rubric_attached"]
        ),
        "supported_standalone_cells_missing_anti_cheat_cards": sum(
            1 for row in ledger_rows
            if row["mode"] == "standalone_100m_weights" and row["has_truthful_100m_support"] and not row["cell_anti_cheat_cards_attached"]
        ),
        "supported_standalone_cells_missing_gemma_comparison": sum(
            1 for row in ledger_rows
            if row["mode"] == "standalone_100m_weights" and row["has_truthful_100m_support"] and not row["cross_model_comparison_attached"]
        ),
        "supported_standalone_cells_missing_checkpoint_hash": sum(
            1 for row in ledger_rows
            if row["mode"] == "standalone_100m_weights" and row["has_truthful_100m_support"] and not row["checkpoint_or_harness_run_attached"]
        ),
        "anti_hack_challenge_families_passed": anti_hack_families_passed,
        "anti_hack_challenge_families_total": anti_hack_total_families,
        "languages_with_any_truthful_support": sorted(supported_language_counter),
        "supported_skill_coverage_by_language": dict(sorted(supported_language_counter.items())),
        "supported_language_count": len(supported_language_counter),
        "supported_skill_count": len(supported_skill_counter),
        "missing_skills_by_language": missing_skills_by_language,
        "languages_with_full_9_skill_support": fully_supported_languages,
    }

    failures: list[str] = []
    if anti_hack.get("passed") is not True:
        failures.append("global_anti_hack_gate_not_passed")
    if runbook.get("passed") is not True:
        failures.append("stage9750_runbook_not_passed")
    if metrics["records"] != 72:
        failures.append("unexpected_record_count")
    if metrics["supported_standalone_cells"] != 13:
        failures.append("unexpected_supported_standalone_cell_count")
    if metrics["cells_with_expert_rubric_attached"] != 0:
        failures.append("unexpected_expert_rubric_evidence_present")
    if metrics["cells_with_anti_cheat_cards_attached"] != 0:
        failures.append("unexpected_anti_cheat_cards_present")
    if metrics["supported_language_count"] != 4:
        failures.append("expected_truthful_support_in_all_required_languages_missing")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "closest_supported_standalone_cells": closest_cells,
        "records": ledger_rows,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)

    contract = load_json(CONTRACT)
    anti_hack = load_json(ANTI_HACK)
    acceptance_ledger = load_json(ACCEPTANCE_LEDGER)
    truthful_support = load_json(TRUTHFUL_SUPPORT)
    runbook = load_json(RUNBOOK)
    ledger = build_gap_ledger(contract, anti_hack, acceptance_ledger, truthful_support, runbook)
    LEDGER.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    next_step = (
        "Attach expert-maintainer rubric scores and cell-specific anti-cheat cards for the 13 supported standalone cells, "
        "then recover the missing Gemma runner surface so those same cells can be scored head-to-head before any broader training claim."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": ledger["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **ledger["metrics"],
        },
        "artifacts": {
            "ledger": str(LEDGER.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Materialized a multilingual expert-eval coverage gap ledger that separates global anti-hacking readiness from the still-missing per-cell maintainer rubric, anti-cheat card, checkpoint, and Gemma comparison evidence.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9751 Expert Eval Coverage Gap Ledger",
        "",
        f"Passed: `{summary['passed']}`",
        f"Standalone supported cells: `{summary['metrics']['supported_standalone_cells']}`",
        f"Languages with any truthful support: `{summary['metrics']['languages_with_any_truthful_support']}`",
        f"Cells with expert rubric attached: `{summary['metrics']['cells_with_expert_rubric_attached']}`",
        f"Cells with anti-cheat cards attached: `{summary['metrics']['cells_with_anti_cheat_cards_attached']}`",
        "",
        "The current repo already has a passed global anti-eval-hacking gate, but it still lacks per-cell expert-maintainer rubric evidence and per-cell anti-cheat cards for every acceptance cell, including the 13 standalone cells that already have truthful 100M-side support.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "supported_standalone_cells": summary["metrics"]["supported_standalone_cells"],
        "cells_with_expert_rubric_attached": summary["metrics"]["cells_with_expert_rubric_attached"],
        "cells_with_anti_cheat_cards_attached": summary["metrics"]["cells_with_anti_cheat_cards_attached"],
        "languages_with_any_truthful_support": summary["metrics"]["languages_with_any_truthful_support"],
        "languages_with_full_9_skill_support": summary["metrics"]["languages_with_full_9_skill_support"],
        "next_best_step": next_step,
        "failures": ledger["failures"],
    }, indent=2, sort_keys=True))
    if ledger["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
