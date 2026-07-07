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
STAGE = 9108
NAME = "stage9108_central_graph_gap_walk_remaining_trainer_blockers"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GRAPH = ROOT / "runs/local/artifacts/stage9106_execution_authorization_graph_attachment/central_research_graph_with_execution_authorization_controls.json"
SOURCE_9107 = ROOT / "runs/summaries/stage9107_current_frontier_reconciliation_after_execution_authorization_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CENTRAL_GRAPH_GAP_WALK_REMAINING_TRAINER_BLOCKERS_STAGE9108.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "central_graph_gap_walk_remaining_trainer_blockers.json"

REQUIRED_CONTROL_NODES = [
    "contract:trainer_command_surface_static_v1",
    "contract:trainer_runtime_assertion_inventory_v1",
    "contract:trainer_contract_only_artifact_schema_v1",
    "contract:trainer_execution_authorization_review_v1",
    "gate:execution_requires_explicit_user_request",
    "gate:execution_requires_contract_only_artifacts",
    "gate:execution_requires_final_pre_execution_audit",
    "gate:execution_requires_one_run_training_ticket",
]

REMAINING_BLOCKERS = [
    {
        "priority": 1,
        "blocker": "explicit_user_execution_request_missing",
        "required_next": "Do not execute until the user explicitly requests a specific one-run trainer action.",
        "authority_closed": True,
    },
    {
        "priority": 2,
        "blocker": "real_source_output_ticket_not_instantiated",
        "required_next": "Design/instantiate a source-output ticket before any real row bodies, route cards, or source/repository bodies are read.",
        "authority_closed": True,
    },
    {
        "priority": 3,
        "blocker": "route_cards_not_materialized",
        "required_next": "Materialize route cards only after a source-output ticket and row-sample judge path authorize metadata/data access.",
        "authority_closed": True,
    },
    {
        "priority": 4,
        "blocker": "route_to_loss_translation_not_materialized",
        "required_next": "Translate approved route cards to row-level loss masks only after route-card materialization passes.",
        "authority_closed": True,
    },
    {
        "priority": 5,
        "blocker": "trainer_contract_only_artifacts_not_materialized",
        "required_next": "Run a future trainer contract-only instance only after locked manifest, schema lock, loss masks, and artifact schema inputs exist.",
        "authority_closed": True,
    },
    {
        "priority": 6,
        "blocker": "final_pre_execution_audit_missing",
        "required_next": "Run a final pre-execution audit after contract-only artifacts pass and before any one-run ticket.",
        "authority_closed": True,
    },
    {
        "priority": 7,
        "blocker": "one_run_training_ticket_missing",
        "required_next": "Instantiate a one-run ticket only after explicit user request, passing contract-only artifacts, and final pre-execution audit.",
        "authority_closed": True,
    },
]

NEXT_SAFE_BRANCHES = [
    "metadata-only real-data availability preflight design without /arxiv writes",
    "source-output ticket design without reading row bodies",
    "contract-only dry-run input materialization design without invocation",
    "central graph attachment for this gap-walk result",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    graph = load_json(GRAPH)
    s9107 = load_json(SOURCE_9107)
    node_ids = {str(node.get("id")) for node in graph.get("nodes", []) if node.get("id")}
    present_controls = sorted(node for node in REQUIRED_CONTROL_NODES if node in node_ids)
    missing_controls = sorted(node for node in REQUIRED_CONTROL_NODES if node not in node_ids)
    authority_rows = sum(1 for node in graph.get("nodes", []) if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    checks = {
        "source_stage9107_passed": s9107.get("passed") is True,
        "base_graph_present": GRAPH.exists(),
        "required_control_nodes_present": not missing_controls,
        "remaining_blockers_recorded": len(REMAINING_BLOCKERS) >= 7,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "authority_rows_zero": authority_rows == 0,
        "registry_frontier_stage9107": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9107,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CENTRAL_GRAPH_GAP_WALK_REMAINING_TRAINER_BLOCKERS_NO_EXECUTION",
        "graph_source": str(GRAPH.relative_to(ROOT)),
        "present_control_nodes": present_controls,
        "missing_control_nodes": missing_controls,
        "remaining_blockers": REMAINING_BLOCKERS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "required_control_nodes": len(REQUIRED_CONTROL_NODES),
            "present_control_nodes": len(present_controls),
            "missing_control_nodes": len(missing_controls),
            "remaining_blockers": len(REMAINING_BLOCKERS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "authority_rows": authority_rows,
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
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
        "decision": "Central graph gap walk confirms trainer command, runtime assertion, contract-only artifact schema, and execution authorization controls are present. Remaining blockers are source/output ticket, route-card materialization, route-to-loss translation, contract-only artifact materialization, final pre-execution audit, one-run ticket, and explicit user execution request. Execution and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9107, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if card["metrics"].get("missing_control_nodes") != 0:
        failures.append("missing_control_nodes")
    if card["metrics"].get("remaining_blockers", 0) < 7:
        failures.append("remaining_blockers_incomplete")
    for key in [
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "runtime_assertions_executed_now",
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
    for key in ["candidate_rows_materialized", "model_input_rows_now"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
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
        "decision": card["decision"] if not failures else "Central graph gap walk for remaining trainer blockers failed.",
        "next_best_step": "Design metadata-only real-data availability preflight without /arxiv writes; keep execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9108 Central Graph Gap Walk Remaining Trainer Blockers",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "No data, trainer, contract-only mode, runtime assertion, model forward, cleanup, or /arxiv operation is invoked.",
        "",
        f"Control nodes present: `{card['metrics']['present_control_nodes']}/{card['metrics']['required_control_nodes']}`",
        f"Remaining blockers: `{card['metrics']['remaining_blockers']}`",
        "",
        "Remaining blockers:",
        "",
        *[f"{row['priority']}. `{row['blocker']}` - {row['required_next']}" for row in REMAINING_BLOCKERS],
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
    marker = "## Stage9108 Central Graph Gap Walk Remaining Trainer Blockers"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9108 confirms trainer command, runtime assertion, contract-only artifact schema, and execution authorization controls are present in the central graph. Remaining blockers are source/output ticket, route-card materialization, route-to-loss translation, contract-only artifacts, final pre-execution audit, one-run ticket, and explicit user execution request.",
            "",
            "No data access, route-card materialization, route-to-loss translation, compiler handoff, trainer dry run, trainer invocation, contract-only invocation, runtime assertion execution, model forward, decoder CE, denoise CE, runtime, cleanup, /arxiv IO, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
