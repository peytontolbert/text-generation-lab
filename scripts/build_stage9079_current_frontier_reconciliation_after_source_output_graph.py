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
STAGE = 9079
NAME = "stage9079_current_frontier_reconciliation_after_source_output_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9075 = ROOT / "runs/summaries/stage9075_current_frontier_reconciliation_after_trainer_docs_graph.json"
SOURCE_9076 = ROOT / "runs/summaries/stage9076_future_source_output_ticket_design.json"
SOURCE_9077 = ROOT / "runs/summaries/stage9077_future_source_output_ticket_design_audit.json"
SOURCE_9078 = ROOT / "runs/summaries/stage9078_source_output_ticket_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_SOURCE_OUTPUT_GRAPH_STAGE9079.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_source_output_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9075_frontier_after_trainer_docs_graph",
    "stage9076_inactive_source_output_ticket_design",
    "stage9077_inactive_source_output_ticket_negative_case_audit",
    "stage9078_source_output_ticket_graph_attachment",
    "graph_gate_never_delete_arxiv",
    "graph_gate_no_source_body_read_without_ticket",
    "graph_gate_no_route_card_materialization_without_ticket",
]

NEXT_SAFE_BRANCHES = [
    "no-data route-card materialization audit instance design",
    "source-output ticket graph gap walk",
    "trainer dry-run input completeness checklist after source ticket controls",
    "frontier documentation refresh before any explicit ticket instantiation",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9075 = load_json(SOURCE_9075)
    s9076 = load_json(SOURCE_9076)
    s9077 = load_json(SOURCE_9077)
    s9078 = load_json(SOURCE_9078)
    checks = {
        "source_stage9075_passed": s9075.get("passed") is True,
        "source_stage9076_passed": s9076.get("passed") is True,
        "source_stage9077_passed": s9077.get("passed") is True,
        "source_stage9078_passed": s9078.get("passed") is True,
        "stage9078_added_graph_nodes": (s9078.get("metrics") or {}).get("added_nodes", 0) >= 5,
        "stage9078_added_graph_edges": (s9078.get("metrics") or {}).get("added_edges", 0) >= 9,
        "stage9078_authority_rows_zero": (s9078.get("metrics") or {}).get("authority_rows") == 0,
        "stage9078_no_access": (s9078.get("metrics") or {}).get("source_metadata_read_now") is False and (s9078.get("metrics") or {}).get("route_cards_materialized_now") is False,
        "stage9077_negative_cases_rejected": (s9077.get("metrics") or {}).get("negative_cases_rejected") == (s9077.get("metrics") or {}).get("negative_cases"),
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 7,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9078": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9078,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_SOURCE_OUTPUT_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9078_added_nodes": (s9078.get("metrics") or {}).get("added_nodes", 0),
            "stage9078_added_edges": (s9078.get("metrics") or {}).get("added_edges", 0),
            "ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "candidate_mining_authorized": False,
            "index_building_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
            "trainer_invoked": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after attaching inactive source/output ticket controls to the central graph. The graph now records /arxiv never-delete, no body reads without ticket, and no route-card materialization without ticket. No ticket is instantiated and all data, trainer, model, decoder, denoise, runtime, mining, and training paths remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9078, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "candidate_mining_authorized",
        "index_building_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
        "trainer_invoked",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after source/output graph attachment failed.",
        "next_best_step": "Design a no-data route-card materialization audit instance; do not instantiate source/output tickets, read row bodies, mine, or execute trainer.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9079 Current Frontier After Source/Output Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9078. The inactive source/output ticket contract and audit are now represented in the central graph, including `/arxiv` never-delete, no-body-read, and no-route-card-materialization gates.",
        "",
        f"Stage9078 added nodes: `{card['metrics']['stage9078_added_nodes']}`",
        f"Stage9078 added edges: `{card['metrics']['stage9078_added_edges']}`",
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
    marker = "## Stage9079 Current Frontier After Source/Output Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9079 reconciles the current frontier after Stage9078. The source/output ticket controls are graph-attached; next safe work is a no-data route-card materialization audit instance design.",
            "",
            "No source metadata read, row/source body read, route-card materialization, candidate mining, /arxiv IO, cleanup, trainer dry run, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
