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
STAGE = 9082
NAME = "stage9082_route_card_audit_instance_graph_attachment"
BASE_GRAPH = ROOT / "runs/local/artifacts/stage9078_source_output_ticket_graph_attachment/central_research_graph_with_source_output_ticket.json"
SOURCE_9080 = ROOT / "runs/summaries/stage9080_no_data_route_card_materialization_audit_instance_design.json"
SOURCE_9081 = ROOT / "runs/summaries/stage9081_no_data_route_card_materialization_audit_instance_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_CARD_AUDIT_INSTANCE_GRAPH_ATTACHMENT_STAGE9082.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_route_card_audit_instance.json"
CARD = OUT_DIR / "route_card_audit_instance_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:route_card_materialization_audit_instance_inactive_v1", "kind": "contract", "node_type": "contract", "status": "inactive_no_data_instance_design", "summary": "runs/summaries/stage9080_no_data_route_card_materialization_audit_instance_design.json", "authority": AUTHORITY_CLOSED},
    {"id": "audit:route_card_materialization_audit_instance_negative_cases_v1", "kind": "audit", "node_type": "audit", "status": "negative_cases_rejected", "summary": "runs/summaries/stage9081_no_data_route_card_materialization_audit_instance_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:route_card_instance_requires_source_output_ticket", "kind": "gate", "node_type": "gate", "status": "required_before_route_card_materialization", "authority": AUTHORITY_CLOSED},
    {"id": "gate:route_card_instance_blocks_compiler_handoff", "kind": "gate", "node_type": "gate", "status": "required_before_compiler_handoff", "authority": AUTHORITY_CLOSED},
    {"id": "gate:route_card_instance_blocks_trainer_dry_run", "kind": "gate", "node_type": "gate", "status": "required_before_trainer_dry_run", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:route_card_materialization_audit_instance_inactive_v1", "audited_by", "audit:route_card_materialization_audit_instance_negative_cases_v1"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "requires", "contract:source_output_ticket_inactive_v1"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "requires", "gate:route_card_instance_requires_source_output_ticket"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "requires", "gate:no_route_card_materialization_without_ticket"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "requires", "gate:no_source_body_read_without_ticket"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "blocks", "operation:route_card_materialization"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "blocks", "operation:compiler_handoff"),
    ("contract:route_card_materialization_audit_instance_inactive_v1", "blocks", "operation:trainer_execution"),
    ("gate:route_card_instance_blocks_compiler_handoff", "blocks", "gate:long_context_compiler_handoff_blocker_v1"),
    ("gate:route_card_instance_blocks_trainer_dry_run", "blocks", "contract:trainer_dry_run_recovered_contract_v1"),
    ("audit:route_card_materialization_audit_instance_negative_cases_v1", "rejects", "failure:route_cards_materialized_now"),
    ("audit:route_card_materialization_audit_instance_negative_cases_v1", "rejects", "failure:compiler_handoff_ready_now"),
    ("audit:route_card_materialization_audit_instance_negative_cases_v1", "rejects", "failure:trainer_dry_run_ready_now"),
]

PLACEHOLDER_TARGET_PREFIXES = {
    "contract:": "contract",
    "audit:": "audit",
    "gate:": "gate",
    "operation:": "operation",
    "failure:": "failure",
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
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source_9080 = load_json(SOURCE_9080)
    source_9081 = load_json(SOURCE_9081)
    graph = load_json(BASE_GRAPH)
    nodes = {str(node.get("id")): dict(node) for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = sum(1 for node in NEW_NODES if add_node(nodes, node))
    added_edges = 0
    for source, relation, target in NEW_EDGES:
        ensure_placeholder(nodes, source)
        ensure_placeholder(nodes, target)
        added_edges += int(add_edge(edges, source, relation, target))
    out_graph = {
        **graph,
        "version": NAME,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": sorted(nodes.values(), key=lambda row: str(row.get("id"))),
        "edges": sorted(edges, key=lambda row: (str(row.get("source")), str(row.get("relation")), str(row.get("target")))),
        "authority": dict(AUTHORITY_CLOSED),
    }
    present_nodes = {node.get("id") for node in out_graph["nodes"]}
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out_graph["edges"]}
    authority_rows = sum(1 for node in out_graph["nodes"] if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    checks = {
        "source_stage9080_passed": source_9080.get("passed") is True,
        "source_stage9081_passed": source_9081.get("passed") is True,
        "base_graph_present": BASE_GRAPH.exists(),
        "new_nodes_present": {node["id"] for node in NEW_NODES}.issubset(present_nodes),
        "new_edges_present": set(NEW_EDGES).issubset(present_edges),
        "source_output_ticket_node_present": "contract:source_output_ticket_inactive_v1" in present_nodes,
        "negative_cases_rejected": (source_9081.get("metrics") or {}).get("negative_cases_rejected") == (source_9081.get("metrics") or {}).get("negative_cases"),
        "authority_rows_zero": authority_rows == 0,
        "registry_frontier_stage9081": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9081,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "ROUTE_CARD_AUDIT_INSTANCE_GRAPH_ATTACHMENT_NO_DATA",
        "graph": out_graph,
        "new_node_ids": [node["id"] for node in NEW_NODES],
        "new_edges": [list(edge) for edge in NEW_EDGES],
        "checks": checks,
        "metrics": {
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(out_graph["nodes"]),
            "graph_edges": len(out_graph["edges"]),
            "authority_rows": authority_rows,
            "instance_instantiated_now": False,
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "training_authorized": False,
            "model_forward_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attached inactive route-card materialization audit instance controls to the central graph. Route-card materialization, compiler handoff, trainer dry run, model execution, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9081, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "instance_instantiated_now",
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "route_cards_materialized_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "training_authorized",
        "model_forward_attempted",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    built = build_card(registry)
    graph = built.pop("graph")
    failures = validate_card(built, registry)
    GRAPH.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CARD.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **built["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "graph": str(GRAPH.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": built["decision"] if not failures else "Route-card audit instance graph attachment failed.",
        "next_best_step": "Reconcile current frontier after route-card audit instance graph attachment; do not instantiate any ticket or materialize route cards.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9082 Route-Card Audit Instance Graph Attachment",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Attached the inactive route-card materialization audit instance and its negative-case audit to the central graph.",
        "",
        f"Added nodes: `{built['metrics']['added_nodes']}`",
        f"Added edges: `{built['metrics']['added_edges']}`",
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
    marker = "## Stage9082 Route-Card Audit Instance Graph Attachment"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9082 attaches the inactive route-card materialization audit instance and negative-case audit to the central graph. Compiler handoff and trainer dry-run remain blocked behind source/output and route-card gates.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
