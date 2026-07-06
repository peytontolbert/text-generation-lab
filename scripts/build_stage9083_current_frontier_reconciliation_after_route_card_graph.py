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
STAGE = 9083
NAME = "stage9083_current_frontier_reconciliation_after_route_card_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9079 = ROOT / "runs/summaries/stage9079_current_frontier_reconciliation_after_source_output_graph.json"
SOURCE_9080 = ROOT / "runs/summaries/stage9080_no_data_route_card_materialization_audit_instance_design.json"
SOURCE_9081 = ROOT / "runs/summaries/stage9081_no_data_route_card_materialization_audit_instance_audit.json"
SOURCE_9082 = ROOT / "runs/summaries/stage9082_route_card_audit_instance_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_ROUTE_CARD_GRAPH_STAGE9083.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_route_card_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9079_frontier_after_source_output_graph",
    "stage9080_inactive_route_card_audit_instance_design",
    "stage9081_inactive_route_card_audit_instance_negative_case_audit",
    "stage9082_route_card_audit_instance_graph_attachment",
    "graph_gate_route_card_requires_source_output_ticket",
    "graph_gate_route_card_blocks_compiler_handoff",
    "graph_gate_route_card_blocks_trainer_dry_run",
]

NEXT_SAFE_BRANCHES = [
    "trainer dry-run input completeness checklist after route-card graph controls",
    "central graph gap walk for remaining manifest/trainer blockers",
    "current frontier documentation refresh",
    "future explicit ticket instantiation design only after user authorization",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9079 = load_json(SOURCE_9079)
    s9080 = load_json(SOURCE_9080)
    s9081 = load_json(SOURCE_9081)
    s9082 = load_json(SOURCE_9082)
    checks = {
        "source_stage9079_passed": s9079.get("passed") is True,
        "source_stage9080_passed": s9080.get("passed") is True,
        "source_stage9081_passed": s9081.get("passed") is True,
        "source_stage9082_passed": s9082.get("passed") is True,
        "stage9082_added_graph_nodes": (s9082.get("metrics") or {}).get("added_nodes", 0) >= 5,
        "stage9082_added_graph_edges": (s9082.get("metrics") or {}).get("added_edges", 0) >= 13,
        "stage9082_authority_rows_zero": (s9082.get("metrics") or {}).get("authority_rows") == 0,
        "stage9082_route_cards_closed": (s9082.get("metrics") or {}).get("route_cards_materialized_now") is False,
        "stage9081_negative_cases_rejected": (s9081.get("metrics") or {}).get("negative_cases_rejected") == (s9081.get("metrics") or {}).get("negative_cases"),
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 7,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9082": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9082,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_ROUTE_CARD_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9082_added_nodes": (s9082.get("metrics") or {}).get("added_nodes", 0),
            "stage9082_added_edges": (s9082.get("metrics") or {}).get("added_edges", 0),
            "instance_instantiated_now": False,
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
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
        "decision": "Frontier reconciled after route-card audit instance graph attachment. Source/output ticket controls and route-card audit instance controls are graph-visible, but no ticket, data access, route-card materialization, compiler handoff, trainer dry run, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9082, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "instance_instantiated_now",
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after route-card graph attachment failed.",
        "next_best_step": "Refresh trainer dry-run input completeness checklist after route-card graph controls; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9083 Current Frontier After Route-Card Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9082. The inactive route-card materialization audit instance is graph-visible and blocks compiler handoff and trainer dry-run readiness.",
        "",
        f"Stage9082 added nodes: `{card['metrics']['stage9082_added_nodes']}`",
        f"Stage9082 added edges: `{card['metrics']['stage9082_added_edges']}`",
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
    marker = "## Stage9083 Current Frontier After Route-Card Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9083 reconciles the current frontier after Stage9082. Route-card audit instance controls are graph-visible; next safe work is a trainer dry-run input completeness checklist refresh.",
            "",
            "No ticket, data access, route-card materialization, compiler handoff, trainer dry run, model forward, decoder CE, denoise CE, runtime, /arxiv IO, cleanup, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
