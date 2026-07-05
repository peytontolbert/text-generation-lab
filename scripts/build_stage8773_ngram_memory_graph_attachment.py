#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8773
NAME = "stage8773_ngram_memory_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8770_eval_trace_v2_skill_tool_graph_attachment/central_research_graph_with_eval_trace_v2_skill_tool.json"
SOURCES = [
    ROOT / "runs/summaries/stage8771_ngram_repetition_style_detectors_readiness.json",
    ROOT / "runs/summaries/stage8772_memory_retrieval_evaluator_readiness.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NGRAM_MEMORY_GRAPH_ATTACHMENT_STAGE8773.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}


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
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [s.get("stage_name", str(i)) for i, s in enumerate(summaries) if s.get("passed") is not True]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    ngram = "support_module:ngram_repetition_style_detectors"
    memory = "support_module:memory_retrieval_evaluator"
    added_nodes += int(add_node(nodes, {"id": ngram, "kind": "support_module", "node_type": "support_module", "name": "ngram_repetition_style_detectors", "status": "ready_non_authority_decoder_denoise_ranker_features", "summary": str(SOURCES[0].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {"id": memory, "kind": "support_module", "node_type": "support_module", "name": "memory_retrieval_evaluator", "status": "ready_no_execution_memory_quality_gate", "summary": str(SOURCES[1].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    for downstream in ["support_module:dataset_junk_ood_ranker_v1", "support_module:curriculum_compiler", "objective:bounded_decoder_ce", "objective:denoise_repair", "builder:source_backed_patch_operator"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, ngram, "provides_ranker_features_for", downstream)
        add_edge(edges, memory, "provides_memory_quality_gate_for", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_ngram_memory.json"
    nodes_path = OUT_DIR / "central_research_graph_with_ngram_memory_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_ngram_memory_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached n-gram/style detectors and memory retrieval evaluator to the central graph as no-authority support modules." if not failures else "N-gram/memory graph attachment failed.",
        "next_best_step": "Recover source-backed patch operator builder under gate_status_contract, then cost_budget_scheduler if still missing.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "ngram_memory_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8773 Ngram Memory Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached n-gram/style detector and memory retrieval evaluator support modules.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
