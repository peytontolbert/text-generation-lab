#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8690_program_state_extractors_graph_attachment/central_research_graph_with_program_state_extractors.json"
SUMMARY_IN = ROOT / "runs/summaries/stage8690_context_packer_lost_in_middle_readiness.json"
STAGE = 8691
NAME = "stage8691_v27_context_packer_graph_attachment"
OUT_DIR = ROOT / f"runs/local/artifacts/{NAME}"
SUMMARY = ROOT / "runs/summaries/stage8691_context_packer_graph_attachment.json"
DOC = ROOT / "docs/CONTEXT_PACKER_GRAPH_ATTACHMENT_STAGE8691.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_body_authorized": False,
    "gemma_authorized": False,
    "promotion_ready": False,
}


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if any(existing.get("id") == node["id"] for existing in nodes):
        return False
    nodes.append(node)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    edge = {"source": source, "relation": relation, "target": target, "evidence_source": NAME}
    if any(e.get("source") == source and e.get("relation") == relation and e.get("target") == target for e in edges):
        return False
    edges.append(edge)
    return True


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_registry(card: dict[str, Any]) -> None:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8")) if REGISTRY.exists() else {"stages": []}
    stages = [row for row in registry.get("stages", []) if row.get("stage") != STAGE]
    stages.append({"stage": STAGE, "name": NAME, "summary_path": str(SUMMARY), "artifact_dir": str(OUT_DIR), "passed": card["passed"], "authority_rows": card["metrics"]["authority_rows"], "created_at": card["created_at_utc"]})
    registry["stages"] = sorted(stages, key=lambda row: int(row.get("stage", -1)))
    registry["latest_stage"] = STAGE
    registry["latest_name"] = NAME
    registry["latest_summary_path"] = str(SUMMARY)
    registry["updated_at"] = card["created_at_utc"]
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    stage8690 = json.loads(SUMMARY_IN.read_text(encoding="utf-8"))
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    added_nodes = 0
    added_edges = 0

    new_nodes = [
        {"id": "support_module:context_packer_v1", "kind": "support_module", "name": "context_packer_v1", "role": "budgeted evidence packing with leakage blocking and lost-in-middle ordering", "status": "ready_partial", "summary": str(SUMMARY_IN.relative_to(ROOT)), "authority": AUTHORITY_CLOSED},
        {"id": "support_module:lost_in_middle_ranker", "kind": "support_module", "name": "lost_in_middle_ranker", "role": "place high-value evidence at context front/back", "status": "ready_partial", "authority": AUTHORITY_CLOSED},
        {"id": "support_module:memory_retrieval_evaluator", "kind": "support_module", "name": "memory_retrieval_evaluator", "role": "flag stale duplicate contaminated memory before promotion or packing", "status": "ready_partial", "authority": AUTHORITY_CLOSED},
        {"id": "control_execution:stage8690_context_packer_readiness", "kind": "control_execution", "name": "stage8690_context_packer_readiness", "passed": stage8690.get("passed"), "metrics": stage8690.get("metrics", {}), "authority": AUTHORITY_CLOSED},
    ]
    for node in new_nodes:
        added_nodes += int(add_node(nodes, node))

    links = [
        ("control_execution:stage8690_context_packer_readiness", "implements_or_audits", "support_module:context_packer_v1"),
        ("support_module:context_packer_v1", "uses", "support_module:hybrid_retrieval_fusion"),
        ("support_module:context_packer_v1", "uses", "support_module:knowledge_graph_memory_store"),
        ("support_module:context_packer_v1", "feeds", "architecture_layer:encoder_decoder_seq2seq"),
        ("support_module:context_packer_v1", "protects", "control_card:leakage:source_lineage_guard"),
        ("support_module:lost_in_middle_ranker", "submodule_of", "support_module:context_packer_v1"),
        ("support_module:memory_retrieval_evaluator", "submodule_of", "support_module:context_packer_v1"),
        ("support_module:context_packer_v1", "precedes", "model_family:state_space_mamba"),
    ]
    for source, relation, target in links:
        added_edges += int(add_edge(edges, source, relation, target))

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = NAME
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED
    full = OUT_DIR / "central_research_graph_with_context_packer.json"
    nodes_path = OUT_DIR / "central_research_graph_with_context_packer_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_context_packer_edges.jsonl"
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(nodes_path, nodes)
    write_jsonl(edges_path, edges)

    expected_node_ids = {node["id"] for node in new_nodes}
    present_node_ids = {node.get("id") for node in nodes}
    missing_expected_nodes = sorted(expected_node_ids - present_node_ids)
    failures = []
    if not stage8690.get("passed"):
        failures.append("stage8690_not_passed")
    if missing_expected_nodes:
        failures.append("missing_expected_context_packer_nodes:" + ",".join(missing_expected_nodes))
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {"failures": failures, "added_nodes": added_nodes, "added_edges": added_edges, "graph_nodes": len(nodes), "graph_edges": len(edges), "authority_rows": 0},
        "artifacts": {"graph": str(full.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Context packer/lost-in-middle/memory evaluator is attached to the central graph." if not failures else "Context packer graph attachment failed; repair listed failures.",
        "next_best_step": "Recover training telemetry, then runtime verifier loop; keep training and runtime closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "context_packer_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(f"""# Stage {STAGE}: Context Packer Graph Attachment\n\nPassed: `{card['passed']}`\n\n- added nodes: `{added_nodes}`\n- added edges: `{added_edges}`\n- graph nodes: `{len(nodes)}`\n- graph edges: `{len(edges)}`\n\nThis attaches `context_packer_v1`, `lost_in_middle_ranker`, and `memory_retrieval_evaluator` to the central graph.\n\nAll authority remains closed.\n""", encoding="utf-8")
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
