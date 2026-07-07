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
STAGE = 9111
NAME = "stage9111_metadata_only_preflight_graph_attachment"
BASE_GRAPH = ROOT / "runs/local/artifacts/stage9106_execution_authorization_graph_attachment/central_research_graph_with_execution_authorization_controls.json"
SOURCE_9109 = ROOT / "runs/summaries/stage9109_metadata_only_real_data_availability_preflight_design.json"
SOURCE_9110 = ROOT / "runs/summaries/stage9110_metadata_only_real_data_availability_preflight_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "METADATA_ONLY_PREFLIGHT_GRAPH_ATTACHMENT_STAGE9111.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_metadata_only_preflight_controls.json"
CARD = OUT_DIR / "metadata_only_preflight_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:metadata_only_real_data_availability_preflight_v1", "kind": "contract", "node_type": "contract", "status": "metadata_only_no_arxiv_access", "summary": "runs/summaries/stage9109_metadata_only_real_data_availability_preflight_design.json", "authority": AUTHORITY_CLOSED},
    {"id": "audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "kind": "audit", "node_type": "audit", "status": "negative_cases_rejected", "summary": "runs/summaries/stage9110_metadata_only_real_data_availability_preflight_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:metadata_preflight_blocks_arxiv_access", "kind": "gate", "node_type": "gate", "status": "blocking_current_arxiv_access", "authority": AUTHORITY_CLOSED},
    {"id": "gate:metadata_preflight_blocks_row_source_reads", "kind": "gate", "node_type": "gate", "status": "blocking_current_row_and_source_reads", "authority": AUTHORITY_CLOSED},
    {"id": "gate:metadata_preflight_blocks_arxiv_writes_cleanup", "kind": "gate", "node_type": "gate", "status": "blocking_current_writes_and_cleanup", "authority": AUTHORITY_CLOSED},
    {"id": "gate:metadata_preflight_requires_source_output_ticket_for_body_reads", "kind": "gate", "node_type": "gate", "status": "blocking_future_source_body_reads_without_ticket", "authority": AUTHORITY_CLOSED},
    {"id": "gate:metadata_preflight_requires_route_card_ticket_for_compiler_handoff", "kind": "gate", "node_type": "gate", "status": "blocking_future_compiler_handoff_without_ticket", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:metadata_only_real_data_availability_preflight_v1", "audited_by", "audit:metadata_only_real_data_availability_preflight_negative_cases_v1"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "requires", "gate:metadata_preflight_blocks_arxiv_access"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "requires", "gate:metadata_preflight_blocks_row_source_reads"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "requires", "gate:metadata_preflight_blocks_arxiv_writes_cleanup"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "requires", "gate:metadata_preflight_requires_source_output_ticket_for_body_reads"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "requires", "gate:metadata_preflight_requires_route_card_ticket_for_compiler_handoff"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:arxiv_access"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:arxiv_stat"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:dataset_row_read"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:dataset_parquet_group_read"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:repository_source_body_read"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:write_to_arxiv"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:data_mining"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:route_card_materialization"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:route_to_loss_translation"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:trainer_execution"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:network_upload"),
    ("contract:metadata_only_real_data_availability_preflight_v1", "blocks", "operation:cleanup_execution"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:arxiv_access_performed"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:dataset_rows_loaded"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:repository_source_bodies_loaded"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:arxiv_write_authorized"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:trainer_executed_now"),
    ("audit:metadata_only_real_data_availability_preflight_negative_cases_v1", "rejects", "failure:cleanup_authorized_now"),
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
    if any(edge.get("source") == source and edge.get("relation") == relation and edge.get("target") == target for edge in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9109 = load_json(SOURCE_9109)
    s9110 = load_json(SOURCE_9110)
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
        "source_stage9109_passed": s9109.get("passed") is True,
        "source_stage9110_passed": s9110.get("passed") is True,
        "base_graph_present": BASE_GRAPH.exists(),
        "new_nodes_present": {node["id"] for node in NEW_NODES}.issubset(present_nodes),
        "new_edges_present": set(NEW_EDGES).issubset(present_edges),
        "execution_authorization_contract_present": "contract:trainer_execution_authorization_review_v1" in present_nodes,
        "stage9110_negative_cases_rejected": (s9110.get("metrics") or {}).get("negative_cases_rejected") == (s9110.get("metrics") or {}).get("negative_cases"),
        "authority_rows_zero": authority_rows == 0,
        "registry_frontier_stage9110": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9110,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "METADATA_ONLY_PREFLIGHT_GRAPH_ATTACHMENT_NO_ARXIV_ACCESS",
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
            "arxiv_access_performed": False,
            "arxiv_stat_performed": False,
            "dataset_rows_loaded": False,
            "dataset_parquet_groups_read": False,
            "repository_source_bodies_loaded": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attached metadata-only real-data availability preflight controls to the central graph. /arxiv access/stat, dataset row reads, parquet group reads, repository source-body reads, /arxiv writes, mining, route-card materialization, route-to-loss translation, trainer invocation, model forward, decoder CE, denoise CE, runtime, uploads, cleanup, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9110, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "arxiv_access_performed",
        "arxiv_stat_performed",
        "dataset_rows_loaded",
        "dataset_parquet_groups_read",
        "repository_source_bodies_loaded",
        "arxiv_write_authorized",
        "data_mining_authorized",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "network_upload_performed",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
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
        "decision": built["decision"] if not failures else "Metadata-only preflight graph attachment failed.",
        "next_best_step": "Reconcile current frontier after metadata-only preflight graph attachment; keep /arxiv access and training closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9111 Metadata-Only Preflight Graph Attachment",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Attached metadata-only real-data availability preflight controls to the central graph.",
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
    marker = "## Stage9111 Metadata-Only Preflight Graph Attachment"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9111 attaches Stage9109/9110 metadata-only real-data availability preflight controls to the central graph. The graph now explicitly blocks `/arxiv` access/stat, dataset row reads, parquet group reads, repository source-body reads, `/arxiv` writes, mining, route-card materialization, route-to-loss translation, trainer invocation, model forward, decoder CE, denoise CE, runtime, uploads, cleanup, and training until later ticketed gates authorize each action.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
