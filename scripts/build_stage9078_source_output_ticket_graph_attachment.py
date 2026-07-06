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
STAGE = 9078
NAME = "stage9078_source_output_ticket_graph_attachment"
BASE_GRAPH = ROOT / "runs/local/artifacts/stage9074_trainer_docs_graph_attachment/central_research_graph_with_trainer_docs_contract.json"
SOURCE_9076 = ROOT / "runs/summaries/stage9076_future_source_output_ticket_design.json"
SOURCE_9077 = ROOT / "runs/summaries/stage9077_future_source_output_ticket_design_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_OUTPUT_TICKET_GRAPH_ATTACHMENT_STAGE9078.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_source_output_ticket.json"
CARD = OUT_DIR / "source_output_ticket_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:source_output_ticket_inactive_v1", "kind": "contract", "node_type": "contract", "status": "inactive_no_access_ticket_design", "summary": "runs/summaries/stage9076_future_source_output_ticket_design.json", "authority": AUTHORITY_CLOSED},
    {"id": "audit:source_output_ticket_negative_cases_v1", "kind": "audit", "node_type": "audit", "status": "negative_cases_rejected", "summary": "runs/summaries/stage9077_future_source_output_ticket_design_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:never_delete_arxiv", "kind": "gate", "node_type": "gate", "status": "permanent_backup_root_guard", "authority": AUTHORITY_CLOSED},
    {"id": "gate:no_source_body_read_without_ticket", "kind": "gate", "node_type": "gate", "status": "required_before_source_body_access", "authority": AUTHORITY_CLOSED},
    {"id": "gate:no_route_card_materialization_without_ticket", "kind": "gate", "node_type": "gate", "status": "required_before_route_card_materialization", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:source_output_ticket_inactive_v1", "audited_by", "audit:source_output_ticket_negative_cases_v1"),
    ("contract:source_output_ticket_inactive_v1", "requires", "gate:never_delete_arxiv"),
    ("contract:source_output_ticket_inactive_v1", "requires", "gate:no_source_body_read_without_ticket"),
    ("contract:source_output_ticket_inactive_v1", "requires", "gate:no_route_card_materialization_without_ticket"),
    ("gate:never_delete_arxiv", "blocks", "operation:delete_arxiv"),
    ("gate:no_source_body_read_without_ticket", "blocks", "operation:repository_source_body_read"),
    ("gate:no_route_card_materialization_without_ticket", "blocks", "operation:route_card_materialization"),
    ("contract:source_output_ticket_inactive_v1", "required_before", "gate:long_context_route_card_materialization_audit_v1"),
    ("contract:source_output_ticket_inactive_v1", "required_before", "contract:trainer_dry_run_recovered_contract_v1"),
]

PLACEHOLDER_TARGET_PREFIXES = {
    "contract:": "contract",
    "audit:": "audit",
    "gate:": "gate",
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
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source_9076 = load_json(SOURCE_9076)
    source_9077 = load_json(SOURCE_9077)
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
        "source_stage9076_passed": source_9076.get("passed") is True,
        "source_stage9077_passed": source_9077.get("passed") is True,
        "base_graph_present": BASE_GRAPH.exists(),
        "new_nodes_present": {node["id"] for node in NEW_NODES}.issubset(present_nodes),
        "new_edges_present": set(NEW_EDGES).issubset(present_edges),
        "arxiv_delete_guard_present": "gate:never_delete_arxiv" in present_nodes,
        "negative_cases_rejected": (source_9077.get("metrics") or {}).get("negative_cases_rejected") == (source_9077.get("metrics") or {}).get("negative_cases"),
        "authority_rows_zero": authority_rows == 0,
        "registry_frontier_stage9077": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9077,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "SOURCE_OUTPUT_TICKET_GRAPH_ATTACHMENT_NO_ACCESS",
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
            "ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
            "training_authorized": False,
            "model_forward_attempted": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attached inactive source/output ticket controls to the central graph. The graph now records /arxiv never-delete, no body reads without ticket, and no route-card materialization without ticket. No access or execution is authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9077, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
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
        "decision": built["decision"] if not failures else "Source/output ticket graph attachment failed.",
        "next_best_step": "Reconcile current frontier after source/output ticket graph attachment; do not instantiate the ticket yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9078 Source/Output Ticket Graph Attachment",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Attached the inactive source/output ticket contract and audit to the central graph. This is metadata-only and grants no access.",
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
    marker = "## Stage9078 Source/Output Ticket Graph Attachment"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9078 attaches the inactive source/output ticket contract and audit to the central graph. The graph now records `/arxiv` never-delete, no body reads without ticket, and no route-card materialization without ticket.",
            "",
            "No source metadata read, row/source body read, route-card materialization, candidate mining, /arxiv IO, cleanup, trainer dry run, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
