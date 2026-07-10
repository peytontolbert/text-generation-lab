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
STAGE = 9764
NAME = "stage9764_gemma_recovery_and_eval_readiness_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "gemma_recovery_and_eval_readiness_contract.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GEMMA_RECOVERY_AND_EVAL_READINESS_CONTRACT_STAGE9764.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

GAP_LEDGER = ROOT / "runs/local/artifacts/stage9751_expert_eval_coverage_gap_ledger/expert_eval_coverage_gap_ledger.json"
STANDALONE_PACKETS = ROOT / "runs/local/artifacts/stage9752_supported_standalone_review_packets/supported_standalone_review_packets.jsonl"
HARNESS_PACKETS = ROOT / "runs/local/artifacts/stage9756_full_product_harness_review_packets/full_product_harness_review_packets.jsonl"
HARNESS_PREP_AUDIT = ROOT / "runs/local/artifacts/stage9762_harness_prep_completion_audit/harness_prep_completion_audit.json"
GEMMA_GAP_AUDIT = ROOT / "runs/local/artifacts/stage9763_gemma_presence_and_runner_gap_audit/gemma_presence_and_runner_gap_audit.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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


def _top_ready_now_cells(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for packet in packets:
        rows.append({
            "cell_key": packet.get("cell_key"),
            "language_family": packet.get("language_family"),
            "skill_area": packet.get("skill_area"),
            "priority_rank": packet.get("priority_rank"),
            "priority_score": packet.get("priority_score"),
            "ready_now_tasks": [
                "expert_maintainer_rubric_review",
                "prepare_cell_specific_anti_cheat_review",
            ],
            "review_packet_paths": packet.get("review_packet_paths"),
        })
    rows.sort(key=lambda row: (int(row.get("priority_rank") or 9999), str(row.get("cell_key") or "")))
    return rows


def build_contract(
    gap_ledger: dict[str, Any],
    standalone_packets: list[dict[str, Any]],
    harness_packets: list[dict[str, Any]],
    harness_prep_audit: dict[str, Any],
    gemma_gap_audit: dict[str, Any],
) -> dict[str, Any]:
    failures: list[str] = []
    gap_metrics = gap_ledger.get("metrics") if isinstance(gap_ledger.get("metrics"), dict) else {}
    harness_metrics = harness_prep_audit.get("metrics") if isinstance(harness_prep_audit.get("metrics"), dict) else {}
    gemma_metrics = gemma_gap_audit.get("metrics") if isinstance(gemma_gap_audit.get("metrics"), dict) else {}

    if gap_ledger.get("passed") is not True:
        failures.append("stage9751_gap_ledger_not_passed")
    if harness_prep_audit.get("passed") is not True:
        failures.append("stage9762_harness_prep_audit_not_passed")
    if gemma_gap_audit.get("passed") is not True:
        failures.append("stage9763_gemma_gap_audit_not_passed")
    if len(standalone_packets) != 13:
        failures.append("standalone_packet_count_not_13")
    if len(harness_packets) != 36:
        failures.append("harness_packet_count_not_36")
    if int(harness_metrics.get("truthful_queue_entries_after_harness_prep_completion") or 0) != 26:
        failures.append("remaining_ready_now_task_count_not_26")
    if int(gap_metrics.get("supported_standalone_cells") or 0) != 13:
        failures.append("supported_standalone_cells_not_13")

    top_standalone = _top_ready_now_cells(standalone_packets)
    first_standalone = standalone_packets[0] if standalone_packets else {}
    first_harness = harness_packets[0] if harness_packets else {}
    standalone_template = first_standalone.get("expert_maintainer_review_template") if isinstance(first_standalone.get("expert_maintainer_review_template"), dict) else {}
    standalone_anti_cheat = first_standalone.get("anti_cheat_review_template") if isinstance(first_standalone.get("anti_cheat_review_template"), dict) else {}
    harness_template = first_harness.get("harness_execution_template") if isinstance(first_harness.get("harness_execution_template"), dict) else {}

    contract = {
        "passed": not failures,
        "failures": failures,
        "operational_state": {
            "blocker_state": gemma_gap_audit.get("blocker_state"),
            "standalone_ready_now_tasks_remaining": harness_metrics.get("truthful_queue_entries_after_harness_prep_completion"),
            "supported_standalone_cells": gap_metrics.get("supported_standalone_cells"),
            "harness_prep_tasks_already_complete": harness_metrics.get("harness_prep_tasks_completed"),
            "standalone_gemma_runner_present": gemma_metrics.get("standalone_gemma_runner_present"),
            "full_product_harness_runner_present": gemma_metrics.get("full_product_harness_runner_present"),
            "gemma_12b_present": gemma_metrics.get("gemma_12b_present"),
        },
        "phase_1_ready_now_evidence": {
            "scope": "finish the remaining standalone review evidence while runner recovery proceeds separately",
            "remaining_task_count": harness_metrics.get("truthful_queue_entries_after_harness_prep_completion"),
            "tasks_per_supported_cell": 2,
            "required_tasks": [
                "expert_maintainer_rubric_review",
                "prepare_cell_specific_anti_cheat_review",
            ],
            "top_cells_in_order": top_standalone[:13],
            "top_queue_entry": (
                str(top_standalone[0]["cell_key"]) + "::expert_maintainer_rubric_review"
                if top_standalone else None
            ),
        },
        "phase_2_gemma_asset_recovery": {
            "blocker_state": gemma_gap_audit.get("blocker_state"),
            "candidate_roots_seen_on_arxiv": gemma_gap_audit.get("arxiv_scan", {}).get("gemma_candidate_roots"),
            "weight_like_files_found": gemma_gap_audit.get("arxiv_scan", {}).get("gemma_weight_like_files"),
            "required_asset_evidence": [
                "gemma12b_weight_file_or_directory_path",
                "config_json_path",
                "tokenizer_asset_path",
                "provenance_note_for_mount_or_recovery_source",
            ],
            "recovery_rule": (
                "If Gemma-12B already exists outside the repo, record exact mount paths and hashable artifact references; "
                "otherwise recover or authorize Gemma-12B assets before any same-surface comparison claim."
            ),
        },
        "phase_3_runner_wiring": {
            "standalone_runner_contract": {
                "runner_present_now": gemma_metrics.get("standalone_gemma_runner_present"),
                "required_output_path": first_standalone.get("same_surface_gemma_review_slot", {}).get("output_path"),
                "required_bundle_fields": [
                    "prompt_surface_hash_gemma12b",
                    "score_gemma12b",
                    "same_surface_verified",
                    "hundred_m_beats_gemma12b",
                ],
                "must_match_prompt_surface_hash_100m": first_standalone.get("merge_ready_bundle_template", {})
                .get("same_surface_comparison", {})
                .get("prompt_surface_hash_100m"),
            },
            "harness_runner_contract": {
                "runner_present_now": gemma_metrics.get("full_product_harness_runner_present"),
                "required_artifacts": harness_template.get("required_artifacts"),
                "sample_output_paths": first_harness.get("review_packet_paths"),
                "runner_status": harness_template.get("runner_status"),
            },
        },
        "phase_4_eval_readiness": {
            "expert_maintainer_rubric_version": standalone_template.get("rubric_version"),
            "expert_maintainer_subskills": standalone_template.get("subskills_required"),
            "expert_maintainer_subskill_count": len(standalone_template.get("subskills_required") or []),
            "anti_cheat_challenge_families": standalone_anti_cheat.get("challenge_families"),
            "anti_cheat_challenge_family_count": standalone_anti_cheat.get("challenge_family_count"),
            "coverage_statement": (
                "The current expert-maintainer eval surface already checks maintainer-relevant execution behaviors "
                "including intent understanding, symbol binding, edit localization, minimal operator choice, test creation, "
                "verifier prediction, safe repair-or-abstain, patch minimality, hallucination avoidance, and contentful final output. "
                "The anti-cheat surface already checks six challenge families, but per-cell review evidence is still missing."
            ),
        },
        "authority": dict(AUTHORITY_CLOSED),
    }
    return contract


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    contract = build_contract(
        load_json(GAP_LEDGER),
        load_jsonl(STANDALONE_PACKETS),
        load_jsonl(HARNESS_PACKETS),
        load_json(HARNESS_PREP_AUDIT),
        load_json(GEMMA_GAP_AUDIT),
    )
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Work the 26 remaining standalone review tasks first, starting with "
        "standalone_100m_weights::python::symbol_binding::expert_maintainer_rubric_review, while separately recovering "
        "Gemma-12B assets and wiring one standalone Gemma runner plus one full-product harness runner into the existing packet slots."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": contract["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "standalone_ready_now_tasks_remaining": contract["operational_state"]["standalone_ready_now_tasks_remaining"],
            "supported_standalone_cells": contract["operational_state"]["supported_standalone_cells"],
            "harness_prep_tasks_already_complete": contract["operational_state"]["harness_prep_tasks_already_complete"],
            "gemma_12b_present": contract["operational_state"]["gemma_12b_present"],
            "standalone_gemma_runner_present": contract["operational_state"]["standalone_gemma_runner_present"],
            "full_product_harness_runner_present": contract["operational_state"]["full_product_harness_runner_present"],
            "expert_maintainer_subskill_count": contract["phase_4_eval_readiness"]["expert_maintainer_subskill_count"],
            "anti_cheat_challenge_family_count": contract["phase_4_eval_readiness"]["anti_cheat_challenge_family_count"],
        },
        "artifacts": {
            "contract": str(CONTRACT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": "Converted the Gemma blocker and eval-readiness state into an operational contract that names the remaining ready-now evidence work, the exact missing Gemma assets, the runner output schemas, and the maintainer-eval coverage already present in the review packets.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9764 Gemma Recovery And Eval Readiness Contract",
        "",
        f"Passed: `{summary['passed']}`",
        f"Remaining standalone ready-now tasks: `{summary['metrics']['standalone_ready_now_tasks_remaining']}`",
        f"Supported standalone cells: `{summary['metrics']['supported_standalone_cells']}`",
        f"Harness prep tasks already complete: `{summary['metrics']['harness_prep_tasks_already_complete']}`",
        f"Gemma-12B present: `{summary['metrics']['gemma_12b_present']}`",
        f"Standalone Gemma runner present: `{summary['metrics']['standalone_gemma_runner_present']}`",
        f"Full harness runner present: `{summary['metrics']['full_product_harness_runner_present']}`",
        f"Expert-maintainer subskills: `{summary['metrics']['expert_maintainer_subskill_count']}`",
        f"Anti-cheat challenge families: `{summary['metrics']['anti_cheat_challenge_family_count']}`",
        "",
        "This stage turns the current frontier into an operational sequence: finish the 26 remaining standalone rubric and anti-cheat tasks, recover Gemma-12B assets, and wire the missing standalone and harness runner outputs into the already-materialized packet slots.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "standalone_ready_now_tasks_remaining": summary["metrics"]["standalone_ready_now_tasks_remaining"],
        "gemma_12b_present": summary["metrics"]["gemma_12b_present"],
        "standalone_gemma_runner_present": summary["metrics"]["standalone_gemma_runner_present"],
        "full_product_harness_runner_present": summary["metrics"]["full_product_harness_runner_present"],
        "expert_maintainer_subskill_count": summary["metrics"]["expert_maintainer_subskill_count"],
        "anti_cheat_challenge_family_count": summary["metrics"]["anti_cheat_challenge_family_count"],
        "failures": contract["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if contract["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
