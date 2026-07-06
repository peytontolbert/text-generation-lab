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
STAGE = 9063
NAME = "stage9063_long_context_compiler_loss_mask_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage9058_long_context_route_card_schema_graph_attachment/central_research_graph_with_long_context_route_card_schema.json"
SOURCE_9061 = ROOT / "runs/summaries/stage9061_long_context_compiler_handoff_blocker_audit.json"
SOURCE_9062 = ROOT / "runs/summaries/stage9062_long_context_loss_mask_compiler_preflight.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_COMPILER_LOSS_MASK_GRAPH_ATTACHMENT_STAGE9063.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_long_context_compiler_loss_mask_blockers.json"
CARD = OUT_DIR / "long_context_compiler_loss_mask_graph_attachment_card.json"

NEW_NODES = [
    {"id": "gate:long_context_compiler_handoff_blocker_v1", "kind": "gate", "node_type": "gate", "status": "no_data_blocker", "summary": "runs/summaries/stage9061_long_context_compiler_handoff_blocker_audit.json", "authority": AUTHORITY_CLOSED},
    {"id": "preflight:long_context_loss_mask_compiler_v1", "kind": "preflight", "node_type": "preflight", "status": "loss_mask_translation_preflight_only", "summary": "runs/summaries/stage9062_long_context_loss_mask_compiler_preflight.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:long_context_route_card_materialization_audit_v1", "kind": "gate", "node_type": "gate", "status": "future_required_before_compiler", "summary": "runs/summaries/stage9059_long_context_route_card_materialization_audit_contract.json", "authority": AUTHORITY_CLOSED},
    {"id": "gate:split_overlap_audit", "kind": "gate", "node_type": "gate", "status": "required_before_compiler", "authority": AUTHORITY_CLOSED},
    {"id": "gate:telemetry_contract", "kind": "gate", "node_type": "gate", "status": "required_before_compiler", "authority": AUTHORITY_CLOSED},
    {"id": "loss_mask:long_context_route_to_trainer_translation", "kind": "loss_mask", "node_type": "loss_mask", "status": "preflight_only_decoder_denoise_runtime_closed", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("gate:long_context_compiler_handoff_blocker_v1", "guards", "compiler_stage:curriculum_compiler"),
    ("schema:long_context_route_card_v1", "blocked_by", "gate:long_context_compiler_handoff_blocker_v1"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:long_context_source_output_ticket_v1"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:long_context_route_card_materialization_audit_v1"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "support_module:dataset_junk_ood_ranker_v1"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:shortcut_baseline_audit"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:counterfactual_obligation_audit"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:split_overlap_audit"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "loss_mask:long_context_route_to_trainer_translation"),
    ("gate:long_context_compiler_handoff_blocker_v1", "requires", "gate:telemetry_contract"),
    ("preflight:long_context_loss_mask_compiler_v1", "translates", "schema:long_context_route_card_v1"),
    ("preflight:long_context_loss_mask_compiler_v1", "emits_preflight", "loss_mask:long_context_route_to_trainer_translation"),
    ("preflight:long_context_loss_mask_compiler_v1", "blocks", "objective:bounded_decoder_ce"),
    ("preflight:long_context_loss_mask_compiler_v1", "blocks", "objective:output_repair_denoise"),
    ("preflight:long_context_loss_mask_compiler_v1", "blocks", "objective:runtime_reward"),
]

PLACEHOLDER_TARGET_PREFIXES = {
    "gate:": "gate",
    "support_module:": "support_module",
    "compiler_stage:": "compiler_stage",
    "objective:": "objective",
    "loss_mask:": "loss_mask",
    "schema:": "schema",
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
    source_9061 = load_json(SOURCE_9061)
    source_9062 = load_json(SOURCE_9062)
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
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out["edges"]}
    failures = []
    if source_9061.get("passed") is not True:
        failures.append("source_stage9061_not_passed")
    if source_9062.get("passed") is not True:
        failures.append("source_stage9062_not_passed")
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
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": built["authority_rows"], "failures": built["failures"], "added_nodes": built["added_nodes"], "added_edges": built["added_edges"], "graph_nodes": len(graph["nodes"]), "graph_edges": len(graph["edges"]), "compiler_ready_rows_now": 0, "training_authorized": False, "decoder_ce_authorized": False, "denoise_ce_authorized": False},
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT))},
        "decision": "Attached long-context compiler handoff and route-to-trainer loss-mask blockers to the central graph; all training and decoder/denoise/runtime paths remain closed.",
        "next_best_step": "Continue no-data recovery by refreshing the training readiness blocker matrix against Stage9061-9063 controls.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9063 Long Context Compiler/Loss-Mask Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached Stage9061 compiler handoff blocker and Stage9062 route-to-trainer loss-mask preflight to the central graph. This remains no-data and no-training.",
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
