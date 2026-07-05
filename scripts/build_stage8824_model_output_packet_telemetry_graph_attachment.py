#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8824
NAME = "stage8824_model_output_packet_telemetry_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8821_heldout_non_ce_decoder_eval_design_graph_attachment/central_research_graph_with_heldout_non_ce_decoder_eval_design.json"
SOURCE = ROOT / "runs/summaries/stage8823_model_output_packet_telemetry_contract_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_PACKET_TELEMETRY_GRAPH_ATTACHMENT_STAGE8824.md"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = node["id"]
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = node
    return True


def add_edge(edges: list[dict[str, Any]], src: str, relation: str, dst: str) -> None:
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": NAME}
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    card_src = json.loads(SOURCE.read_text(encoding="utf-8"))
    failures = [] if card_src.get("passed") is True else [card_src.get("stage_name")]
    m = card_src.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added = 0
    contract = "contract:model_output_packet_telemetry_v1"
    packet_objective = "objective:future_model_output_packet_schema"
    probe_readiness = "objective:future_probe_packet_readiness_audit"
    added += int(add_node(nodes, {
        "id": contract,
        "kind": "contract",
        "node_type": "contract",
        "name": "model_output_packet_telemetry_v1",
        "status": "schema_ready_no_execution_not_probe_ready",
        "rows": m.get("rows"),
        "split_counts": m.get("split_counts"),
        "argument_counts": m.get("argument_counts"),
        "required_checks_complete": m.get("missing_required_check_rows") == 0,
        "required_telemetry_complete": m.get("missing_required_telemetry_rows") == 0,
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": probe_readiness,
        "kind": "objective",
        "node_type": "objective",
        "name": "future_probe_packet_readiness_audit",
        "status": "missing_next_recovery_target",
        "purpose": "Validate that any future tiny probe packet conforms to model_output_packet_telemetry_v1 before execution is considered.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        packet_objective,
        "objective:heldout_non_ce_decoder_evaluation_design",
        "objective:bounded_decoder_ce",
        "support_module:traced_eval_observability",
        "support_module:gradient_activation_interpretability",
        "support_module:golden_locked_eval_suite",
        "study_path:transformer_tiny_model_intelligence",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, packet_objective, "materialized_by_contract", contract)
    add_edge(edges, contract, "required_before", probe_readiness)
    add_edge(edges, probe_readiness, "required_before_any_execution_for", "objective:bounded_decoder_ce")
    add_edge(edges, "objective:heldout_non_ce_decoder_evaluation_design", "requires_packet_contract", contract)
    add_edge(edges, "support_module:traced_eval_observability", "records_fields_for", contract)
    add_edge(edges, "support_module:gradient_activation_interpretability", "records_tensor_telemetry_for", contract)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", probe_readiness)
    add_edge(edges, "study_path:transformer_tiny_model_intelligence", "defines_shape_expectations_for", contract)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_model_output_packet_telemetry_contract.json"
    nodes_path = OUT_DIR / "central_research_graph_with_model_output_packet_telemetry_contract_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_model_output_packet_telemetry_contract_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "contract_rows": m.get("rows"), "probe_ready_rows": m.get("probe_ready_rows"), "loss_rows": m.get("loss_rows"), "decoder_ce_eligible_now_rows": m.get("decoder_ce_eligible_now_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "contract_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached model-output packet telemetry contract to graph; next missing target is no-execution future probe packet readiness audit.", "next_best_step": "Build no-execution future probe packet readiness audit. Keep execution/training/CE closed.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "model_output_packet_telemetry_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8824 Model Output Packet Telemetry Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Contract rows: `{metrics['contract_rows']}`", f"Probe-ready rows: `{metrics['probe_ready_rows']}`", f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`", "", "The graph now records `contract:model_output_packet_telemetry_v1` and the next no-execution readiness audit needed before any tiny probe.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
