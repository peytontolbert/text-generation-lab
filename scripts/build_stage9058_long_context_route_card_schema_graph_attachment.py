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
STAGE = 9058
NAME = "stage9058_long_context_route_card_schema_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage9054_long_context_ticket_controls_graph_attachment/central_research_graph_with_long_context_ticket_controls.json"
SOURCE_9057 = ROOT / "runs/summaries/stage9057_long_context_route_card_schema_contract.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_ROUTE_CARD_SCHEMA_GRAPH_ATTACHMENT_STAGE9058.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_long_context_route_card_schema.json"
CARD = OUT_DIR / "long_context_route_card_schema_graph_attachment_card.json"

NEW_NODES = [
    {"id": "schema:long_context_route_card_v1", "kind": "schema", "node_type": "schema", "status": "metadata_only_no_rows", "summary": "runs/summaries/stage9057_long_context_route_card_schema_contract.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:long_context_route_card_required_gates", "kind": "gate", "node_type": "gate", "status": "schema_contract", "authority": AUTHORITY_CLOSED},
]
NEW_EDGES = [
    ("schema:long_context_route_card_v1", "extends", "gate:long_context_source_output_ticket_v1"),
    ("schema:long_context_route_card_v1", "defines_handoff_to", "compiler_stage:curriculum_compiler"),
    ("schema:long_context_route_card_v1", "requires_before_compiler", "support_module:dataset_junk_ood_ranker_v1"),
    ("schema:long_context_route_card_v1", "requires_before_compiler", "gate:shortcut_baseline_audit"),
    ("schema:long_context_route_card_v1", "requires_before_compiler", "gate:counterfactual_obligation_audit"),
    ("schema:long_context_route_card_v1", "keeps_default_closed", "loss_mask:long_context_default_all_false"),
    ("gate:long_context_route_card_required_gates", "guards", "schema:long_context_route_card_v1"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = str(node["id"])
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = dict(node)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    edge = {"source": source, "relation": relation, "target": target, "evidence_source": NAME}
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append(edge)
    return True


def build_card() -> dict[str, Any]:
    source = load_json(SOURCE_9057)
    graph = load_json(BASE)
    nodes = {str(node.get("id")): dict(node) for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = sum(1 for node in NEW_NODES if add_node(nodes, node))
    added_edges = 0
    for source_id, relation, target in NEW_EDGES:
        if target.startswith("loss_mask:") and target not in nodes:
            add_node(nodes, {"id": target, "kind": "loss_mask", "node_type": "loss_mask", "status": "all_false_default", "authority": AUTHORITY_CLOSED})
        added_edges += int(add_edge(edges, source_id, relation, target))
    out = {**graph, "version": NAME, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "nodes": sorted(nodes.values(), key=lambda row: str(row.get("id"))), "edges": sorted(edges, key=lambda row: (str(row.get("source")), str(row.get("relation")), str(row.get("target")))), "authority": AUTHORITY_CLOSED}
    present_nodes = {node.get("id") for node in out["nodes"]}
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out["edges"]}
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9057_not_passed")
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
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": built["authority_rows"], "failures": built["failures"], "added_nodes": built["added_nodes"], "added_edges": built["added_edges"], "graph_nodes": len(graph["nodes"]), "graph_edges": len(graph["edges"]), "route_rows_materialized_now": False, "training_authorized": False},
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT))},
        "decision": "Attached long-context route-card schema contract to the central graph as metadata-only no-row control.",
        "next_best_step": "Continue trainer/compiler no-data recovery or define a future granted-ticket route-card materialization audit. Do not mine/train.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9058 Long Context Route Card Schema Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached the metadata-only route-card schema to the central graph. No real rows, mining, model execution, or training are authorized.", ""]) + "\n", encoding="utf-8")
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
