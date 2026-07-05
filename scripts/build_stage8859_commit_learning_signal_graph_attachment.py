#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8859
NAME = "stage8859_commit_learning_signal_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8852_learning_signal_code_patch_readiness_graph_attachment/central_research_graph_with_learning_signal_code_patch_readiness.json"
SOURCE = ROOT / "runs/summaries/stage8855_commit_learning_signal_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_LEARNING_SIGNAL_GRAPH_ATTACHMENT_STAGE8859.md"
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
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    failures = [] if src.get("passed") is True else [src.get("stage_name")]
    m = src.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added = 0

    contract = "contract:commit_learning_signal_v1"
    gate = "objective:commit_learning_signal_no_mining_gate_audit"
    compiler = "compiler:curriculum_compiler_v1"
    source_lineage = "gate:source_inventory_lineage"
    provenance = "gate:source_provenance"
    contamination = "gate:contamination_leakage_detector"
    locked_eval = "gate:golden_locked_eval_suite"
    junk = "gate:dataset_junk_ood_ranker_v1"
    cluster = "gate:cluster_slice_near_duplicate_detector"

    added += int(add_node(nodes, {
        "id": contract,
        "kind": "contract",
        "node_type": "contract",
        "name": "commit_learning_signal_v1",
        "status": "contract_ready_no_mining_no_training",
        "rows": m.get("rows"),
        "contract_ready_rows": m.get("contract_ready_rows"),
        "target_surfaces": m.get("target_surfaces"),
        "commit_size_buckets": m.get("commit_size_buckets"),
        "required_filter_signals": m.get("required_filter_signals"),
        "required_unit_labels": m.get("required_unit_labels"),
        "purpose": "Defines how git commits become causal edit units for structured maintainer supervision without mining repositories yet.",
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": gate,
        "kind": "objective",
        "node_type": "objective",
        "name": "commit_learning_signal_no_mining_gate_audit",
        "status": "missing_next_recovery_target",
        "purpose": "Audit that commit-learning-signal contract rows are closed, typed, source-gated, and cannot authorize /arxiv repository walking, training, or decoder CE.",
        "authority": AUTHORITY_CLOSED,
    }))

    for node_id in [compiler, source_lineage, provenance, contamination, locked_eval, junk, cluster]:
        add_node(nodes, {"id": node_id, "kind": "support_or_gate", "node_type": "support_or_gate", "authority": AUTHORITY_CLOSED})
    for surface in m.get("target_surfaces", []):
        add_node(nodes, {"id": f"surface:{surface}", "kind": "target_surface", "node_type": "target_surface", "authority": AUTHORITY_CLOSED})
        add_edge(edges, contract, "emits_candidate_surface_after_future_gate", f"surface:{surface}")

    add_edge(edges, compiler, "requires_contract_before_mining", contract)
    add_edge(edges, contract, "required_before", gate)
    for gate_node in [source_lineage, provenance, contamination, locked_eval, junk, cluster]:
        add_edge(edges, contract, "requires_source_gate", gate_node)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_commit_learning_signal_contract.json"
    nodes_path = OUT_DIR / "central_research_graph_with_commit_learning_signal_contract_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_commit_learning_signal_contract_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "source_failures": failures,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "added_nodes": added,
        "commit_contract_rows": m.get("rows"),
        "commit_contract_ready_rows": m.get("contract_ready_rows"),
        "commit_mining_authorized": False,
        "arxiv_repository_walk_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "commit_contract_summary": str(SOURCE.relative_to(ROOT)),
        },
        "decision": "Attached commit-learning-signal contract to graph. Commit mining remains closed.",
        "next_best_step": "Recover commit-learning-signal no-mining gate audit. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "commit_learning_signal_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8859 Commit Learning Signal Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Contract rows: `{metrics['commit_contract_rows']}`",
        f"Contract ready rows: `{metrics['commit_contract_ready_rows']}`",
        f"Commit mining authorized: `{metrics['commit_mining_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
        "The central graph now records commit mining as a closed contract over causal edit units, not a raw repository crawl.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
