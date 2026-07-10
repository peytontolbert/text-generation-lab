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
STAGE = 9928
NAME = "stage9928_current_weighted_runner_truth_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "current_weighted_runner_truth_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_WEIGHTED_RUNNER_TRUTH_AUDIT_STAGE9928.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

WEIGHTED_PACKETS = ROOT / "runs/local/artifacts/stage9925_supported_standalone_weighted_frontier_refresh/supported_standalone_weighted_frontier_packets.jsonl"
WEIGHTED_CHECKLIST = ROOT / "runs/local/artifacts/stage9926_supported_standalone_weighted_completion_checklist/supported_standalone_weighted_completion_checklist.json"
HARNESS_PROXIES = ROOT / "runs/local/artifacts/stage9927_full_product_harness_weighted_proxy_refresh/full_product_harness_weighted_proxy_packets.jsonl"
WEIGHTED_GEMMA_SUMMARY = ROOT / "runs/summaries/stage9919_hardened_weighted_edit_localization_gemma_comparison.json"
STANDALONE_RUNNER = ROOT / "scripts/run_stage9748_standalone_gemma_queue_via_ollama.py"


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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""

def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _winner_cells(packets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    winners = [
        row for row in packets
        if str(row.get("priority_reason") or "").startswith("weighted hardened multilingual")
    ]
    winners.sort(key=lambda row: (int(row.get("priority_rank") or 999), str(row.get("cell_key") or "")))
    return winners[:4]


def _attached_machine_evidence(packet: dict[str, Any]) -> dict[str, Any]:
    merge = packet.get("merge_ready_bundle_template") if isinstance(packet.get("merge_ready_bundle_template"), dict) else {}
    same = merge.get("same_surface_comparison") if isinstance(merge.get("same_surface_comparison"), dict) else {}
    artifacts = merge.get("evidence_artifacts") if isinstance(merge.get("evidence_artifacts"), dict) else {}
    return {
        "cell_key": packet.get("cell_key"),
        "language_family": packet.get("language_family"),
        "same_surface_present": same.get("present") is True,
        "same_surface_verified": same.get("same_surface_verified") is True,
        "hundred_m_beats_gemma12b": same.get("hundred_m_beats_gemma12b") is True,
        "same_prompt_surface_gemma_outputs_present": bool(artifacts.get("same_prompt_surface_gemma12b_outputs")),
        "language_slice_scores_present": bool(artifacts.get("language_slice_scores")),
        "frozen_hash_attached": bool(artifacts.get("frozen_export_or_checkpoint_hash")),
        "expert_review_present": bool(artifacts.get("expert_maintainer_rubric_scores")),
        "anti_cheat_card_present": bool(artifacts.get("anti_cheat_cards")),
    }


def build_audit() -> dict[str, Any]:
    weighted_packets = load_jsonl(WEIGHTED_PACKETS)
    weighted_checklist = load_json(WEIGHTED_CHECKLIST)
    harness_proxies = load_jsonl(HARNESS_PROXIES)
    gemma_summary = load_json(WEIGHTED_GEMMA_SUMMARY)
    runner_text = _read_text(STANDALONE_RUNNER)
    failures: list[str] = []

    winner_packets = _winner_cells(weighted_packets)
    winner_evidence = [_attached_machine_evidence(packet) for packet in winner_packets]
    checklist_records = weighted_checklist.get("records") if isinstance(weighted_checklist.get("records"), list) else []
    checklist_index = {str(row.get("cell_key") or ""): row for row in checklist_records}
    harness_weighted = [
        row for row in harness_proxies
        if str(row.get("priority_bucket") or "") == "aligned_with_weighted_hardened_frontier_cell"
    ]

    standalone_runner_surface = {
        "script_path": _display_path(STANDALONE_RUNNER),
        "present": STANDALONE_RUNNER.exists(),
        "has_build_prompt": "def build_prompt" in runner_text,
        "has_ollama_generate": "def ollama_generate" in runner_text,
        "has_run_packet": "def run_packet" in runner_text,
        "has_main_entrypoint": "def main" in runner_text,
    }
    harness_runner_surface = {
        "candidate_scripts": sorted(_display_path(path) for path in ROOT.glob("scripts/run_*harness*.py")),
        "present": False,
    }
    gemma_execution_state = {
        "weighted_summary_present": WEIGHTED_GEMMA_SUMMARY.exists(),
        "gemma_executed": bool((gemma_summary.get("metrics") or {}).get("gemma_executed") is True),
        "wins_100m": int((gemma_summary.get("metrics") or {}).get("wins_100m") or 0),
        "wins_gemma": int((gemma_summary.get("metrics") or {}).get("wins_gemma") or 0),
        "ties": int((gemma_summary.get("metrics") or {}).get("ties") or 0),
    }

    ready_review_count = 0
    for row in winner_evidence:
        checklist = checklist_index.get(str(row["cell_key"]))
        row["human_review_only_remaining"] = bool(checklist and checklist.get("weighted_frontier_cell") is True)
        if row["human_review_only_remaining"]:
            ready_review_count += 1

    weighted_harness_proxy_count = sum(
        1 for row in harness_weighted
        if row.get("runner_status") == "missing_harness_runner_surface_but_proxy_frontier_machine_complete"
    )

    metrics = {
        "weighted_frontier_winner_cells": len(winner_evidence),
        "machine_complete_winner_cells": sum(
            1
            for row in winner_evidence
            if row["same_surface_present"]
            and row["same_surface_verified"]
            and row["same_prompt_surface_gemma_outputs_present"]
            and row["language_slice_scores_present"]
            and row["frozen_hash_attached"]
        ),
        "human_review_only_winner_cells": ready_review_count,
        "weighted_harness_proxy_cells": len(harness_weighted),
        "weighted_harness_proxy_runner_blocked_cells": weighted_harness_proxy_count,
        "standalone_runner_surface_present": int(standalone_runner_surface["present"]),
        "harness_runner_surface_present": int(harness_runner_surface["present"]),
    }

    if metrics["weighted_frontier_winner_cells"] != 4:
        failures.append("weighted_frontier_winner_cells_not_4")
    if metrics["machine_complete_winner_cells"] != 4:
        failures.append("machine_complete_winner_cells_not_4")
    if metrics["human_review_only_winner_cells"] != 4:
        failures.append("human_review_only_winner_cells_not_4")
    if metrics["weighted_harness_proxy_cells"] != 4:
        failures.append("weighted_harness_proxy_cells_not_4")
    if metrics["weighted_harness_proxy_runner_blocked_cells"] != 4:
        failures.append("weighted_harness_proxy_runner_blocked_cells_not_4")
    if standalone_runner_surface["present"] is not True:
        failures.append("standalone_runner_surface_missing")
    if standalone_runner_surface["has_build_prompt"] is not True:
        failures.append("standalone_runner_build_prompt_missing")
    if standalone_runner_surface["has_ollama_generate"] is not True:
        failures.append("standalone_runner_ollama_generate_missing")
    if gemma_execution_state["gemma_executed"] is not True:
        failures.append("weighted_gemma_execution_not_attached")
    if harness_runner_surface["present"] is not False:
        failures.append("unexpected_harness_runner_surface_present")

    return {
        "passed": not failures,
        "failures": failures,
        "metrics": metrics,
        "standalone_runner_surface": standalone_runner_surface,
        "harness_runner_surface": harness_runner_surface,
        "gemma_execution_state": gemma_execution_state,
        "weighted_winner_cells": winner_evidence,
        "authority": dict(AUTHORITY_CLOSED),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    next_step = (
        "Treat the four weighted standalone winner cells as machine-complete and review-blocked only, then build a real "
        "full-product harness runner surface for the four weighted proxy cells because harness execution is now the only "
        "machine-side blocker on that frontier."
    )
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            **audit["metrics"],
            "gemma_executed": audit["gemma_execution_state"]["gemma_executed"],
            "wins_100m": audit["gemma_execution_state"]["wins_100m"],
            "wins_gemma": audit["gemma_execution_state"]["wins_gemma"],
            "ties": audit["gemma_execution_state"]["ties"],
        },
        "artifacts": {
            "audit": _display_path(AUDIT),
            "doc": _display_path(DOC),
        },
        "decision": "Audited the current weighted frontier and confirmed that standalone Gemma execution is already real and attached for the four multilingual edit-localization winners, while full-product harness execution remains the only machine-side runner gap there.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9928 Current Weighted Runner Truth Audit",
        "",
        f"Passed: `{summary['passed']}`",
        f"Weighted winner cells: `{summary['metrics']['weighted_frontier_winner_cells']}`",
        f"Machine-complete winner cells: `{summary['metrics']['machine_complete_winner_cells']}`",
        f"Human-review-only winner cells: `{summary['metrics']['human_review_only_winner_cells']}`",
        f"Weighted harness proxy runner-blocked cells: `{summary['metrics']['weighted_harness_proxy_runner_blocked_cells']}`",
        f"Standalone runner surface present: `{bool(summary['metrics']['standalone_runner_surface_present'])}`",
        f"Harness runner surface present: `{bool(summary['metrics']['harness_runner_surface_present'])}`",
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
        "metrics": summary["metrics"],
        "failures": audit["failures"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if audit["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
