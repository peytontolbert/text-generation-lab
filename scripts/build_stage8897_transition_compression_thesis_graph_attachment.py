#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8897
NAME = "stage8897_transition_compression_thesis_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8879_closed_gate_status_reconciliation/central_research_graph_with_closed_gate_status_reconciliation.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRANSITION_COMPRESSION_THESIS_STAGE8897.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

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

THESIS_NODES = [
    {
        "id": "thesis:transition_compression_not_world_memory",
        "kind": "research_thesis",
        "name": "transition_compression_not_world_memory",
        "role": "100M model should learn reusable software-state transition operators, not memorize all papers/frameworks/repos",
        "status": "active_contract",
    },
    {
        "id": "model_role:100m_transition_kernel",
        "kind": "model_role",
        "name": "100m_transition_kernel",
        "role": "policy kernel pi(a_t | S_t, R_t, O_t) over software states, retrieved knowledge, and tool observations",
        "status": "active_target_role",
    },
    {
        "id": "external_memory:retrieval_long_tail_facts",
        "kind": "external_memory",
        "name": "retrieval_long_tail_facts",
        "role": "stores package/version/framework/paper/repo-specific facts outside the 100M weights",
        "status": "required_support",
    },
    {
        "id": "compiler_stage:raw_corpus_to_structured_operators",
        "kind": "curriculum_compiler_stage",
        "name": "raw_corpus_to_structured_operators",
        "role": "compress raw code, papers, docs, issues, tests, traces, and diffs into canonical transition records",
        "status": "required_compiler_contract",
    },
    {
        "id": "paper_modality:research_operator_card",
        "kind": "program_state_modality",
        "name": "research_operator_card",
        "role": "paper-derived operator with problem, assumptions, algorithm, invariants, failure modes, implementation sketch, and tests",
        "status": "missing_or_future_schema",
    },
    {
        "id": "training_objective:transition_prediction",
        "kind": "training_objective",
        "name": "transition_prediction",
        "role": "predict next useful action/state update rather than raw next-token continuation",
        "status": "governing_objective",
    },
    {
        "id": "training_objective:verified_repair_transition",
        "kind": "training_objective",
        "name": "verified_repair_transition",
        "role": "learn corrupted software state -> repair action -> verifier observation -> next state",
        "status": "governing_objective",
    },
    {
        "id": "capacity_contract:parametric_memory_boundary",
        "kind": "capacity_contract",
        "name": "parametric_memory_boundary",
        "role": "compress repeated structure into weights; route arbitrary long-tail details to retrieval/tools/verifiers",
        "status": "active_contract",
    },
]

THESIS_EDGES = [
    ("thesis:transition_compression_not_world_memory", "defines_role", "model_role:100m_transition_kernel"),
    ("thesis:transition_compression_not_world_memory", "requires", "external_memory:retrieval_long_tail_facts"),
    ("thesis:transition_compression_not_world_memory", "requires", "compiler_stage:raw_corpus_to_structured_operators"),
    ("compiler_stage:raw_corpus_to_structured_operators", "produces", "training_objective:transition_prediction"),
    ("compiler_stage:raw_corpus_to_structured_operators", "produces", "training_objective:verified_repair_transition"),
    ("paper_modality:research_operator_card", "feeds", "compiler_stage:raw_corpus_to_structured_operators"),
    ("external_memory:retrieval_long_tail_facts", "conditions", "model_role:100m_transition_kernel"),
    ("training_objective:transition_prediction", "trains", "model_role:100m_transition_kernel"),
    ("training_objective:verified_repair_transition", "trains", "model_role:100m_transition_kernel"),
    ("capacity_contract:parametric_memory_boundary", "governs", "model_role:100m_transition_kernel"),
    ("capacity_contract:parametric_memory_boundary", "routes_long_tail_to", "external_memory:retrieval_long_tail_facts"),
    ("architecture_layer:repo_state_graph_v1", "is_state_view_for", "model_role:100m_transition_kernel"),
    ("architecture_layer:verifier_repair", "provides_observation_for", "training_objective:verified_repair_transition"),
    ("support_module:source_inventory_lineage_tracker", "guards", "compiler_stage:raw_corpus_to_structured_operators"),
    ("support_module:structured_dataset_junk_ranker", "filters", "compiler_stage:raw_corpus_to_structured_operators"),
]

REQUIRED_EXISTING_SUPPORT = [
    "architecture_layer:repo_state_graph_v1",
    "architecture_layer:verifier_repair",
    "support_module:source_inventory_lineage_tracker",
    "support_module:structured_dataset_junk_ranker",
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if any(existing.get("id") == node["id"] for existing in nodes):
        return False
    enriched = {**node, "authority": AUTHORITY_CLOSED, "recovered_from": NAME}
    nodes.append(enriched)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    key = (source, relation, target)
    if any((edge.get("source"), edge.get("relation"), edge.get("target")) == key for edge in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def attach_transition_thesis(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    existing_ids = {node.get("id") for node in nodes}
    missing_support = [node_id for node_id in REQUIRED_EXISTING_SUPPORT if node_id not in existing_ids]
    added_nodes = sum(1 for node in THESIS_NODES if add_node(nodes, node))
    added_edges = sum(1 for source, relation, target in THESIS_EDGES if add_edge(edges, source, relation, target))
    out = {"version": NAME, "nodes": nodes, "edges": edges}
    metrics = {
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "missing_existing_support_nodes": missing_support,
        "thesis_node_count": len(THESIS_NODES),
        "thesis_edge_count": len(THESIS_EDGES),
    }
    return out, metrics


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    out, attach = attach_transition_thesis(graph)
    failures = []
    if not graph:
        failures.append("missing_base_graph")
    if attach["missing_existing_support_nodes"]:
        failures.append("missing_existing_support_nodes")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8896, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    graph_path = OUT_DIR / "central_research_graph_with_transition_compression_thesis.json"
    nodes_path = OUT_DIR / "central_research_graph_with_transition_compression_thesis_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_transition_compression_thesis_edges.jsonl"
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
            **attach,
            "authority_rows": 0,
            "failures": failures,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "data_mining_authorized": False,
        },
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Attached transition-compression thesis: 100M model is a software-state transition kernel, not a parametric world-memory store." if not failures else "Transition-compression thesis attachment failed.",
        "next_best_step": "Use this thesis to judge future data/compiler work: raw sources must become canonical transition records before training; long-tail facts stay in retrieval/tools. Stage8890 still requires explicit authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8897 Transition Compression Thesis",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Central thesis: the 100M maintainer is not a world-memory container. It is a transition kernel over software state, retrieved knowledge, and tool observations.",
        "",
        "Raw code, papers, docs, issues, tests, traces, and diffs must first be compressed by the curriculum compiler into canonical transition records and reusable operators. Long-tail package/version/framework facts remain external in retrieval/tools/verifiers.",
        "",
        "This opens no model execution, training, decoder CE, denoise CE, runtime, `/arxiv` walk, data mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8897 Transition Compression Thesis"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The 100M software maintainer is governed as a transition kernel, not a parametric encyclopedia. Raw papers/frameworks/repos are too large as direct memory; the curriculum compiler must convert them into canonical software-state transition records, research-operator cards, verifier-grounded repair traces, and retrieval-conditioned action examples.",
            "",
            "Weights should store reusable transition operators. Retrieval/tools/verifiers should store and ground long-tail facts. Future mining/training must preserve this division of labor.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
