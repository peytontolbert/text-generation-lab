#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8715_repo_graph_encoder_graph_attachment/central_research_graph_with_repo_graph_encoder.json"
SOURCE = ROOT / "runs/summaries/stage8716_rubric_judge_calibrator_readiness.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8717_rubric_judge_calibrator_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8717_rubric_judge_calibrator_graph_attachment.json"
DOC = ROOT / "docs/RUBRIC_JUDGE_CALIBRATOR_GRAPH_ATTACHMENT_STAGE8717.md"

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
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": "stage8717_rubric_judge_calibrator_graph_attachment"}
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
    module = "support_module:rubric_llm_judge_calibrator"
    added_nodes = 0
    added_nodes += int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "rubric_llm_judge_calibrator", "status": "ready_partial_deterministic_calibration", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    metrics = ["judge_metric:rubric_score", "judge_metric:judge_confidence", "judge_metric:verifier_disagreement", "judge_metric:manual_review_route", "judge_metric:mean_brier"]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "judge_metric", "node_type": "judge_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    for gate in ["gate:judge_verifier_disagreement_blocks_accept", "gate:high_confidence_wrong_requires_manual_review", "gate:rubric_is_not_ground_truth"]:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    for downstream in ["support_module:dataset_junk_ood_ranker_v1", "support_module:curriculum_compiler", "support_module:weak_supervision_label_model", "objective:bounded_decoder_ce"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "calibrates_signal_for", downstream)
    out = {"version": "stage8717_rubric_judge_calibrator_graph_attachment", "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_rubric_judge_calibrator.json"
    nodes_path = OUT_DIR / "central_research_graph_with_rubric_judge_calibrator_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_rubric_judge_calibrator_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": 8717,
        "name": "stage8717_rubric_judge_calibrator_graph_attachment",
        "stage_name": "stage8717_rubric_judge_calibrator_graph_attachment",
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {"authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "metrics_attached": len(metrics), "gates_attached": 3, **AUTHORITY_CLOSED},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached rubric judge calibrator as deterministic verifier-disagreement calibration layer; no judge/model authority opened.",
        "next_best_step": "Recover operator inventory/codelength interfaces before mining/training resumes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "rubric_judge_calibrator_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8717 Rubric Judge Calibrator Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached rubric/verifier calibration metrics and gates. Rubric/LLM judges remain calibration signals only.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
