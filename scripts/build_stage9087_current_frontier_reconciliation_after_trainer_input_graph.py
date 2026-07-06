#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9087
NAME = "stage9087_current_frontier_reconciliation_after_trainer_input_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9083 = ROOT / "runs/summaries/stage9083_current_frontier_reconciliation_after_route_card_graph.json"
SOURCE_9084 = ROOT / "runs/summaries/stage9084_trainer_dry_run_input_completeness_after_route_card_graph.json"
SOURCE_9085 = ROOT / "runs/summaries/stage9085_trainer_dry_run_input_completeness_audit.json"
SOURCE_9086 = ROOT / "runs/summaries/stage9086_trainer_dry_run_input_controls_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_TRAINER_INPUT_GRAPH_STAGE9087.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_trainer_input_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9083_frontier_after_route_card_graph",
    "stage9084_trainer_dry_run_input_completeness_refresh",
    "stage9085_trainer_dry_run_input_completeness_negative_case_audit",
    "stage9086_trainer_dry_run_input_controls_graph_attachment",
    "graph_gate_trainer_requires_source_output_ticket",
    "graph_gate_trainer_requires_route_card_audit_output",
    "graph_gate_route_to_loss_translation_blocked",
    "graph_gate_model_forward_blocked",
]

NEXT_SAFE_BRANCHES = [
    "route-to-trainer-loss translation no-data design",
    "trainer dry-run command surface static audit refresh",
    "central graph gap walk for remaining trainer blockers",
    "future explicit source/output ticket instantiation design only after user authorization",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9083 = load_json(SOURCE_9083)
    s9084 = load_json(SOURCE_9084)
    s9085 = load_json(SOURCE_9085)
    s9086 = load_json(SOURCE_9086)
    checks = {
        "source_stage9083_passed": s9083.get("passed") is True,
        "source_stage9084_passed": s9084.get("passed") is True,
        "source_stage9085_passed": s9085.get("passed") is True,
        "source_stage9086_passed": s9086.get("passed") is True,
        "stage9085_negative_cases_rejected": (s9085.get("metrics") or {}).get("negative_cases_rejected") == (s9085.get("metrics") or {}).get("negative_cases"),
        "stage9086_added_graph_nodes": (s9086.get("metrics") or {}).get("added_nodes", 0) >= 6,
        "stage9086_added_graph_edges": (s9086.get("metrics") or {}).get("added_edges", 0) >= 16,
        "stage9086_authority_rows_zero": (s9086.get("metrics") or {}).get("authority_rows") == 0,
        "stage9086_route_to_loss_closed": (s9086.get("metrics") or {}).get("route_to_loss_translation_ready_now") is False,
        "stage9086_trainer_closed": (s9086.get("metrics") or {}).get("trainer_dry_run_ready_now") is False,
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 8,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9086": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9086,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_TRAINER_INPUT_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9086_added_nodes": (s9086.get("metrics") or {}).get("added_nodes", 0),
            "stage9086_added_edges": (s9086.get("metrics") or {}).get("added_edges", 0),
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "route_to_loss_translation_ready_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after trainer dry-run input controls graph attachment. Source/output ticket, route-card audit, and trainer input completeness controls are graph-visible, but no data access, route-card materialization, route-to-loss translation, compiler handoff, trainer dry run, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9086, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Current frontier reconciliation after trainer input graph attachment failed.",
        "next_best_step": "Design route-to-trainer-loss translation as a no-data artifact; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9087 Current Frontier After Trainer Input Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9086. Trainer dry-run input completeness controls are graph-visible and block route-to-loss translation, compiler handoff, trainer execution, and model forward.",
        "",
        f"Stage9086 added nodes: `{card['metrics']['stage9086_added_nodes']}`",
        f"Stage9086 added edges: `{card['metrics']['stage9086_added_edges']}`",
        "",
        "Next safe branches:",
        "",
        *[f"- {branch}" for branch in NEXT_SAFE_BRANCHES],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9087 Current Frontier After Trainer Input Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9087 reconciles the current frontier after Stage9086. Source/output ticket, route-card audit, and trainer input completeness controls are graph-visible.",
            "",
            "No data access, route-card materialization, route-to-loss translation, compiler handoff, trainer dry run, model forward, decoder CE, denoise CE, runtime, /arxiv IO, cleanup, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
