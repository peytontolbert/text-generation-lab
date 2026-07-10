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
STAGE = 9929
NAME = "stage9929_weighted_harness_runner_plan"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
PLAN = OUT_DIR / "weighted_harness_runner_plan.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "WEIGHTED_HARNESS_RUNNER_PLAN_STAGE9929.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

HARNESS_PACKETS = ROOT / "runs/local/artifacts/stage9927_full_product_harness_weighted_proxy_refresh/full_product_harness_weighted_proxy_packets.jsonl"
RUNNER_TRUTH = ROOT / "runs/local/artifacts/stage9928_current_weighted_runner_truth_audit/current_weighted_runner_truth_audit.json"
WEIGHTED_FRONTIER = ROOT / "runs/local/artifacts/stage9922_current_weighted_hardened_multilingual_frontier_bridge/current_weighted_hardened_multilingual_frontier_bridge.json"
WEIGHTED_TRUTHFUL = ROOT / "runs/local/artifacts/stage9924_current_truthful_weighted_hardened_bridge_after_review_workbook/current_truthful_weighted_hardened_bridge_after_review_workbook.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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


def _weighted_packets(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        row for row in packets
        if str(row.get("priority_bucket") or "") == "aligned_with_weighted_hardened_frontier_cell"
    ]
    rows.sort(key=lambda row: (int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    return rows


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _runner_steps(packet: dict[str, Any]) -> list[str]:
    return [
        "load_weighted_harness_proxy_packet",
        "verify_proxy_standalone_frontier_machine_complete",
        "record_real_harness_run_id_only_after_execution",
        "capture_same_task_pack_artifacts_for_100m_and_gemma_on_identical_task_pack",
        "collect_tool_trace_spans_from_full_product_run",
        "collect_verifier_results_and_patch_minimality_or_abstain_scores",
        "attach_human_rubric_and_cell_specific_anti_cheat_after_machine_artifacts_are_real",
    ]


def _write_cell_plan(packet: dict[str, Any], plan: dict[str, Any]) -> str:
    packet_dir = ROOT / str(packet.get("review_packet_paths", {}).get("packet_dir") or "")
    path = packet_dir / "harness_runner_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return _display(path)


def build_plan() -> dict[str, Any]:
    packets = _weighted_packets(load_jsonl(HARNESS_PACKETS))
    truth = load_json(RUNNER_TRUTH)
    frontier = load_json(WEIGHTED_FRONTIER)
    truthful = load_json(WEIGHTED_TRUTHFUL)
    failures: list[str] = []

    frontier_by_lang = {
        str(row.get("language_family") or ""): row
        for row in (frontier.get("records") or [])
        if isinstance(row, dict)
    }
    truthful_by_lang = {
        str(row.get("language_family") or ""): row
        for row in (truthful.get("records") or [])
        if isinstance(row, dict)
    }

    if truth.get("passed") is not True:
        failures.append("stage9928_not_passed")

    cell_plans: list[dict[str, Any]] = []
    for packet in packets:
        language = str(packet.get("language_family") or "")
        frontier_row = frontier_by_lang.get(language)
        truthful_row = truthful_by_lang.get(language)
        paths = packet.get("review_packet_paths") if isinstance(packet.get("review_packet_paths"), dict) else {}
        if not isinstance(frontier_row, dict):
            failures.append(f"missing_weighted_frontier_record:{language}")
            continue
        if not isinstance(truthful_row, dict):
            failures.append(f"missing_weighted_truthful_record:{language}")
            continue
        required_paths = {
            key: str(paths.get(key) or "")
            for key in [
                "packet_dir",
                "harness_run_id",
                "same_task_pack_as_gemma12b",
                "tool_trace_spans",
                "verifier_results",
                "patch_minimality_or_abstain_scores",
                "expert_maintainer_rubric_scores",
                "anti_cheat_cards",
            ]
        }
        missing_paths = [key for key, rel in required_paths.items() if not rel]
        if missing_paths:
            failures.append(f"missing_packet_paths:{packet.get('cell_key')}:{','.join(missing_paths)}")
            continue
        existing_stub_status = {key: (ROOT / rel).exists() for key, rel in required_paths.items() if key != "packet_dir"}
        if not all(existing_stub_status.values()):
            failures.append(f"missing_stub_file:{packet.get('cell_key')}")
        plan = {
            "cell_key": packet.get("cell_key"),
            "proxy_standalone_cell_key": packet.get("proxy_standalone_cell_key"),
            "language_family": language,
            "skill_area": packet.get("skill_area"),
            "runner_surface_status": "dry_run_contract_ready_real_harness_runtime_still_missing",
            "required_artifacts": list(packet.get("harness_execution_template", {}).get("required_artifacts") or []),
            "artifact_paths": required_paths,
            "existing_stub_status": existing_stub_status,
            "standalone_proxy_frontier": {
                "strict_exact_100m": frontier_row.get("strict_exact_100m"),
                "strict_exact_gemma": frontier_row.get("strict_exact_gemma"),
                "strict_verdict": frontier_row.get("strict_verdict"),
                "same_surface_comparison_stage": frontier_row.get("same_surface_comparison_stage"),
                "same_surface_shortcut_audit_stage": frontier_row.get("same_surface_shortcut_audit_stage"),
            },
            "remaining_machine_gap": "real_full_product_harness_runtime_integration_and_capture",
            "remaining_human_gates": list(truthful_row.get("remaining_human_gates") or []),
            "runner_steps": _runner_steps(packet),
        }
        plan["runner_plan_path"] = _write_cell_plan(packet, plan)
        cell_plans.append(plan)

    metrics = {
        "weighted_harness_proxy_cells": len(cell_plans),
        "cell_plans_written": sum(1 for row in cell_plans if row.get("runner_plan_path")),
        "cells_with_all_stub_paths_present": sum(1 for row in cell_plans if all((row.get("existing_stub_status") or {}).values())),
        "cells_still_missing_real_harness_runtime": sum(1 for row in cell_plans if row.get("remaining_machine_gap") == "real_full_product_harness_runtime_integration_and_capture"),
    }
    if metrics["weighted_harness_proxy_cells"] != 4:
        failures.append("weighted_harness_proxy_cells_not_4")
    if metrics["cell_plans_written"] != 4:
        failures.append("cell_plans_written_not_4")
    if metrics["cells_with_all_stub_paths_present"] != 4:
        failures.append("cells_with_all_stub_paths_present_not_4")
    if metrics["cells_still_missing_real_harness_runtime"] != 4:
        failures.append("cells_still_missing_real_harness_runtime_not_4")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "cell_plans": cell_plans,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    built = build_plan()
    PLAN.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Use the per-cell harness_runner_plan.json files for the four weighted proxy cells to wire a real full-product harness runtime, "
        "because the packet schema, stub files, and standalone proxy evidence are now explicit and the remaining machine gap is only runtime integration."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **built["metrics"],
        },
        "artifacts": {
            "plan": _display(PLAN),
            "doc": _display(DOC),
        },
        "decision": "Materialized per-cell harness runner plans for the four weighted proxy frontier cells so the remaining harness blocker is now a concrete runtime integration task rather than an underspecified packet problem.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9929 Weighted Harness Runner Plan",
        "",
        f"Passed: `{summary['passed']}`",
        f"Weighted harness proxy cells: `{summary['metrics']['weighted_harness_proxy_cells']}`",
        f"Cell plans written: `{summary['metrics']['cell_plans_written']}`",
        f"Cells with all stub paths present: `{summary['metrics']['cells_with_all_stub_paths_present']}`",
        "",
        summary["decision"],
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if summary["passed"]:
        update_registry(summary)
    print(json.dumps({
        "stage": STAGE,
        "passed": summary["passed"],
        "metrics": built["metrics"],
        "failures": built["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if built["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
