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
STAGE = 9067
NAME = "stage9067_trainer_dry_run_controls_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage9063_long_context_compiler_loss_mask_graph_attachment/central_research_graph_with_long_context_compiler_loss_mask_blockers.json"
SOURCE_9065 = ROOT / "runs/summaries/stage9065_trainer_dry_run_input_refresh_after_long_context_controls.json"
SOURCE_9066 = ROOT / "runs/summaries/stage9066_trainer_dry_run_input_negative_case_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_CONTROLS_GRAPH_ATTACHMENT_STAGE9067.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_trainer_dry_run_controls.json"
CARD = OUT_DIR / "trainer_dry_run_controls_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:trainer_dry_run_input_long_context_v1", "kind": "contract", "node_type": "contract", "status": "no_execution_input_contract", "summary": "runs/summaries/stage9065_trainer_dry_run_input_refresh_after_long_context_controls.json", "authority": AUTHORITY_CLOSED},
    {"id": "audit:trainer_dry_run_input_negative_cases_v1", "kind": "audit", "node_type": "audit", "status": "negative_cases_rejected", "summary": "runs/summaries/stage9066_trainer_dry_run_input_negative_case_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_stops_before_model_forward", "kind": "gate", "node_type": "gate", "status": "required_for_dry_run", "authority": AUTHORITY_CLOSED},
    {"id": "gate:no_trainer_row_or_weight_load", "kind": "gate", "node_type": "gate", "status": "required_for_dry_run", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:trainer_dry_run_input_long_context_v1", "requires", "gate:long_context_compiler_handoff_blocker_v1"),
    ("contract:trainer_dry_run_input_long_context_v1", "requires", "preflight:long_context_loss_mask_compiler_v1"),
    ("contract:trainer_dry_run_input_long_context_v1", "requires", "gate:long_context_route_card_materialization_audit_v1"),
    ("contract:trainer_dry_run_input_long_context_v1", "requires", "gate:trainer_stops_before_model_forward"),
    ("contract:trainer_dry_run_input_long_context_v1", "requires", "gate:no_trainer_row_or_weight_load"),
    ("contract:trainer_dry_run_input_long_context_v1", "guards", "trainer:contract_only_dry_run"),
    ("audit:trainer_dry_run_input_negative_cases_v1", "audits", "contract:trainer_dry_run_input_long_context_v1"),
    ("audit:trainer_dry_run_input_negative_cases_v1", "rejects", "failure:missing_long_context_inputs"),
    ("audit:trainer_dry_run_input_negative_cases_v1", "rejects", "failure:model_forward_attempted"),
    ("audit:trainer_dry_run_input_negative_cases_v1", "rejects", "failure:authority_reopened"),
    ("gate:trainer_stops_before_model_forward", "blocks", "operation:model_forward"),
    ("gate:no_trainer_row_or_weight_load", "blocks", "operation:model_weight_load"),
    ("gate:no_trainer_row_or_weight_load", "blocks", "operation:dataset_row_load"),
]

PLACEHOLDER_TARGET_PREFIXES = {
    "gate:": "gate",
    "preflight:": "preflight",
    "contract:": "contract",
    "audit:": "audit",
    "trainer:": "trainer",
    "failure:": "failure",
    "operation:": "operation",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = str(node["id"])
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = dict(node)
    return True


def ensure_placeholder(nodes: dict[str, dict[str, Any]], node_id: str) -> None:
    if node_id in nodes:
        return
    for prefix, kind in PLACEHOLDER_TARGET_PREFIXES.items():
        if node_id.startswith(prefix):
            add_node(nodes, {"id": node_id, "kind": kind, "node_type": kind, "status": "recovered_placeholder", "authority": AUTHORITY_CLOSED})
            return


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    edge = {"source": source, "relation": relation, "target": target, "evidence_source": NAME}
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append(edge)
    return True


def build_card() -> dict[str, Any]:
    source_9065 = load_json(SOURCE_9065)
    source_9066 = load_json(SOURCE_9066)
    graph = load_json(BASE)
    nodes = {str(node.get("id")): dict(node) for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = sum(1 for node in NEW_NODES if add_node(nodes, node))
    added_edges = 0
    for source, relation, target in NEW_EDGES:
        ensure_placeholder(nodes, source)
        ensure_placeholder(nodes, target)
        added_edges += int(add_edge(edges, source, relation, target))
    out = {
        **graph,
        "version": NAME,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": sorted(nodes.values(), key=lambda row: str(row.get("id"))),
        "edges": sorted(edges, key=lambda row: (str(row.get("source")), str(row.get("relation")), str(row.get("target")))),
        "authority": AUTHORITY_CLOSED,
    }
    present_nodes = {node.get("id") for node in out["nodes"]}
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out["edges"] if "source" in edge and "relation" in edge and "target" in edge}
    failures = []
    if source_9065.get("passed") is not True:
        failures.append("source_stage9065_not_passed")
    if source_9066.get("passed") is not True:
        failures.append("source_stage9066_not_passed")
    if not {node["id"] for node in NEW_NODES}.issubset(present_nodes):
        failures.append("missing_nodes")
    if not set(NEW_EDGES).issubset(present_edges):
        failures.append("missing_edges")
    authority_rows = sum(1 for node in out["nodes"] if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    if authority_rows:
        failures.append("authority_open")
    return {"passed": not failures, "failures": failures, "graph": out, "added_nodes": added_nodes, "added_edges": added_edges, "authority_rows": authority_rows}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build_card()
    graph = built.pop("graph")
    GRAPH.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": built["authority_rows"], "failures": built["failures"], "added_nodes": built["added_nodes"], "added_edges": built["added_edges"], "graph_nodes": len(graph["nodes"]), "graph_edges": len(graph["edges"]), "trainer_dry_run_executed_now": False, "model_forward_attempted": False, "training_authorized": False},
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT))},
        "decision": "Attached trainer dry-run input and negative-case controls to the central graph; trainer execution, row loading, model forward, and training remain closed.",
        "next_best_step": "Continue no-data recovery with trainer documentation refresh or final current-frontier reconciliation; do not execute trainer.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9067 Trainer Dry-Run Controls Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached Stage9065 trainer dry-run input contract and Stage9066 negative-case audit to the central graph. This is no-data and no-execution.",
        "",
        f"Next: {card['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
