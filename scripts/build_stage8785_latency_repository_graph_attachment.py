#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8785
NAME = "stage8785_latency_repository_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8782_weak_memory_graph_attachment/central_research_graph_with_weak_memory.json"
SOURCES = [
    ROOT / "runs/summaries/stage8783_latency_resource_observability_readiness.json",
    ROOT / "runs/summaries/stage8784_repository_universe_builder_readiness.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LATENCY_REPOSITORY_GRAPH_ATTACHMENT_STAGE8785.md"
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
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [summary.get("stage_name", str(index)) for index, summary in enumerate(summaries) if summary.get("passed") is not True]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))

    latency = "support_module:latency_resource_observability"
    repo_universe = "support_module:repository_universe_builder"
    added_nodes = 0
    added_nodes += int(add_node(nodes, {
        "id": latency,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "latency_resource_observability",
        "status": "ready_passive_resource_budget_telemetry",
        "summary": str(SOURCES[0].relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": repo_universe,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "repository_universe_builder",
        "status": "ready_no_authority_repo_vector_universe",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))

    for downstream in [
        "support_module:curriculum_compiler",
        "support_module:dataset_junk_ood_ranker_v1",
        "support_module:memory_retrieval_evaluator",
        "support_module:cost_budget_scheduler",
        "objective:source_backed_symbol_binding",
        "objective:source_backed_edit_localization",
        "objective:source_backed_patch_operator",
        "objective:source_backed_verifier_repair",
        "objective:bounded_decoder_ce",
        "objective:denoise_repair",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, latency, "provides_resource_telemetry_for", downstream)
        add_edge(edges, repo_universe, "provides_repo_universe_features_for", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_latency_repository.json"
    nodes_path = OUT_DIR / "central_research_graph_with_latency_repository_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_latency_repository_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "graph_nodes": len(out["nodes"]),
            "graph_edges": len(out["edges"]),
            "added_nodes": added_nodes,
        },
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Attached latency/resource observability and repository universe builder as no-authority support modules." if not failures else "Latency/repository graph attachment failed.",
        "next_best_step": "Recover source-backed verifier-repair builder under gate_status_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "latency_repository_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8785 Latency Repository Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached passive resource observability and no-raw-source repository universe features to the central graph.",
        "",
        "Authority remains closed: no runtime, mining, training, decoder CE, denoise CE, source/body emission, scoring, Gemma, controller merge, memory writes, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
