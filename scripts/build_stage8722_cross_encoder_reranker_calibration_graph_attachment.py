#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8722
NAME = "stage8722_cross_encoder_reranker_calibration_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8719_operator_codelength_interface_graph_attachment/central_research_graph_with_operator_codelength_interface.json"
SOURCE = ROOT / "runs/summaries/stage8721_cross_encoder_reranker_calibration_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CROSS_ENCODER_RERANKER_CALIBRATION_GRAPH_ATTACHMENT_STAGE8722.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
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
    edge = {
        "src": src,
        "edge_type": relation,
        "dst": dst,
        "source": src,
        "relation": relation,
        "target": dst,
        "evidence_source": NAME,
    }
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))

    module = "support_module:cross_encoder_reranker_calibration"
    added_nodes = int(add_node(nodes, {
        "id": module,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "cross_encoder_reranker_calibration",
        "status": "ready_partial_deterministic_calibration",
        "summary": str(SOURCE.relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    metrics = [
        "reranker_metric:task_evidence_probability",
        "reranker_metric:brier",
        "reranker_metric:ece",
        "reranker_metric:high_confidence_wrong",
        "reranker_metric:blocked_leak_locked_pair",
    ]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "reranker_metric", "node_type": "reranker_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    gates = [
        "gate:evidence_pair_leak_blocks_rerank",
        "gate:locked_eval_pair_blocks_rerank",
        "gate:high_confidence_wrong_pair_requires_review",
        "gate:reranker_calibration_required_before_scaleup",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    for upstream in [
        "support_module:repo_span_bm25_retrieval_baseline",
        "support_module:dense_hybrid_retrieval_baseline",
        "support_module:context_packer_v1",
        "support_module:source_lineage_locked_eval_guard",
    ]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in [
        "support_module:context_packer_v1",
        "support_module:curriculum_compiler",
        "support_module:dataset_junk_ood_ranker_v1",
        "objective:symbol_binding",
        "objective:edit_localization",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "calibrates_evidence_for", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_cross_encoder_reranker_calibration.json"
    nodes_path = OUT_DIR / "central_research_graph_with_cross_encoder_reranker_calibration_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_cross_encoder_reranker_calibration_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "graph_nodes": len(out["nodes"]),
            "graph_edges": len(out["edges"]),
            "metrics_attached": len(metrics),
            "gates_attached": len(gates),
            "added_nodes": added_nodes,
        },
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Attached cross-encoder reranker calibration to central graph; retrieval evidence can now be calibrated without model execution.",
        "next_best_step": "Recover dataset_cartography_active_learning, then training_data_attribution_influence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "cross_encoder_reranker_calibration_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join([
            "# Stage8722 Cross-Encoder Reranker Calibration Graph Attachment",
            "",
            f"Passed: `{card['passed']}`",
            "",
            "Attached reranker calibration metrics and gates to the central graph.",
            "",
            "Authority remains closed.",
            "",
        ]),
        encoding="utf-8",
    )
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
