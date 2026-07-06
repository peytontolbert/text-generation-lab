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
STAGE = 9094
NAME = "stage9094_trainer_command_surface_graph_attachment"
BASE_GRAPH = ROOT / "runs/local/artifacts/stage9090_route_to_trainer_loss_translation_graph_attachment/central_research_graph_with_route_to_trainer_loss_translation.json"
SOURCE_9092 = ROOT / "runs/summaries/stage9092_trainer_command_surface_static_refresh.json"
SOURCE_9093 = ROOT / "runs/summaries/stage9093_trainer_command_surface_static_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_COMMAND_SURFACE_GRAPH_ATTACHMENT_STAGE9094.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_trainer_command_surface.json"
CARD = OUT_DIR / "trainer_command_surface_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:trainer_command_surface_static_v1", "kind": "contract", "node_type": "contract", "status": "static_refresh_no_execution", "summary": "runs/summaries/stage9092_trainer_command_surface_static_refresh.json", "authority": AUTHORITY_CLOSED},
    {"id": "audit:trainer_command_surface_static_negative_cases_v1", "kind": "audit", "node_type": "audit", "status": "negative_cases_rejected", "summary": "runs/summaries/stage9093_trainer_command_surface_static_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_command_requires_manifest_flag", "kind": "gate", "node_type": "gate", "status": "required_before_contract_only_or_execution", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_command_requires_mode_flag", "kind": "gate", "node_type": "gate", "status": "required_before_contract_only_or_execution", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_command_requires_loss_mask_audit_flag", "kind": "gate", "node_type": "gate", "status": "required_before_contract_only_or_execution", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_command_blocks_contract_invocation", "kind": "gate", "node_type": "gate", "status": "blocks_contract_only_until_future_authorization", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:trainer_command_surface_static_v1", "audited_by", "audit:trainer_command_surface_static_negative_cases_v1"),
    ("contract:trainer_command_surface_static_v1", "requires", "contract:route_to_trainer_loss_translation_no_data_v1"),
    ("contract:trainer_command_surface_static_v1", "requires", "contract:trainer_dry_run_input_completeness_v1"),
    ("contract:trainer_command_surface_static_v1", "requires", "gate:trainer_command_requires_manifest_flag"),
    ("contract:trainer_command_surface_static_v1", "requires", "gate:trainer_command_requires_mode_flag"),
    ("contract:trainer_command_surface_static_v1", "requires", "gate:trainer_command_requires_loss_mask_audit_flag"),
    ("contract:trainer_command_surface_static_v1", "blocks", "operation:trainer_contract_only_invocation"),
    ("contract:trainer_command_surface_static_v1", "blocks", "operation:trainer_execution"),
    ("contract:trainer_command_surface_static_v1", "blocks", "operation:model_forward"),
    ("gate:trainer_command_blocks_contract_invocation", "blocks", "operation:trainer_contract_only_invocation"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:missing_manifest_flag"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:missing_bounded_decoder_mode"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:missing_safe_cleanup_guard"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:trainer_executed_now"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:contract_only_invoked_now"),
    ("audit:trainer_command_surface_static_negative_cases_v1", "rejects", "failure:model_input_rows_now"),
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
    s9092 = load_json(SOURCE_9092)
    s9093 = load_json(SOURCE_9093)
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
        "source_stage9092_passed": s9092.get("passed") is True,
        "source_stage9093_passed": s9093.get("passed") is True,
        "base_graph_present": BASE_GRAPH.exists(),
        "new_nodes_present": {node["id"] for node in NEW_NODES}.issubset(present_nodes),
        "new_edges_present": set(NEW_EDGES).issubset(present_edges),
        "route_to_loss_contract_present": "contract:route_to_trainer_loss_translation_no_data_v1" in present_nodes,
        "negative_cases_rejected": (s9093.get("metrics") or {}).get("negative_cases_rejected") == (s9093.get("metrics") or {}).get("negative_cases"),
        "authority_rows_zero": authority_rows == 0,
        "registry_frontier_stage9093": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9093,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_COMMAND_SURFACE_GRAPH_ATTACHMENT_NO_EXECUTION",
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
            "trainer_executed_now": False,
            "trainer_dry_run_ready_now": False,
            "contract_only_invoked_now": False,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attached trainer command surface static controls to the central graph. Trainer invocation, contract-only mode, model rows, model forward, decoder CE, denoise CE, runtime, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9093, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "trainer_executed_now",
        "trainer_dry_run_ready_now",
        "contract_only_invoked_now",
        "route_to_loss_translation_ready_now",
        "model_forward_attempted",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["model_input_rows_now", "candidate_rows_materialized"]:
        if card["metrics"].get(key) != 0:
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
        "decision": built["decision"] if not failures else "Trainer command surface graph attachment failed.",
        "next_best_step": "Reconcile current frontier after trainer command surface graph attachment; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9094 Trainer Command Surface Graph Attachment",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Attached trainer command surface static design/audit controls to the central graph.",
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
    marker = "## Stage9094 Trainer Command Surface Graph Attachment"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9094 attaches Stage9092/9093 trainer command surface controls to the central graph. Trainer invocation, contract-only mode, model rows, model forward, decoder CE, denoise CE, runtime, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
