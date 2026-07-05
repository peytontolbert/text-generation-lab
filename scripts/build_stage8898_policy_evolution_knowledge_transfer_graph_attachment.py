#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8898
NAME = "stage8898_policy_evolution_knowledge_transfer_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8897_transition_compression_thesis_graph_attachment/central_research_graph_with_transition_compression_thesis.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POLICY_EVOLUTION_KNOWLEDGE_TRANSFER_STAGE8898.md"
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

EVOLUTION_NODES = [
    {
        "id": "policy_state:static_checkpoint_policy",
        "kind": "policy_state",
        "name": "static_checkpoint_policy",
        "role": "a trained checkpoint is a frozen policy pi_theta_k(a_t | s_t, r_t, o_t) until a new training cycle updates weights",
        "status": "active_contract",
    },
    {
        "id": "loop:evolving_verified_training_cycle",
        "kind": "training_loop",
        "name": "evolving_verified_training_cycle",
        "role": "verified failures, teacher traces, research-transfer records, and repaired transitions update theta_k into theta_k_plus_1",
        "status": "active_contract",
    },
    {
        "id": "policy:knowledge_transfer_policy",
        "kind": "policy_subsystem",
        "name": "knowledge_transfer_policy",
        "role": "turn unfamiliar papers/APIs/framework behavior into implementation plans, tests, patch steps, and verifier-grounded transition records",
        "status": "missing_or_future_schema",
    },
    {
        "id": "compiler_stage:research_to_transition_compiler",
        "kind": "curriculum_compiler_stage",
        "name": "research_to_transition_compiler",
        "role": "extract problem, assumptions, algorithm, invariants, complexity, failure modes, implementation sketch, tests, and integration constraints from new knowledge",
        "status": "required_compiler_contract",
    },
    {
        "id": "dataset_object:verified_transition_record",
        "kind": "dataset_object",
        "name": "verified_transition_record",
        "role": "state + retrieved evidence + action + tool observation + verifier result + next state + reward/value label",
        "status": "canonical_training_object",
    },
    {
        "id": "operator:software_action_transition_algebra",
        "kind": "transition_operator_set",
        "name": "software_action_transition_algebra",
        "role": "localize_failure, retrieve_contract, bind_symbol, choose_test, edit_patch, repair_patch, verify_result, summarize_change",
        "status": "active_target",
    },
    {
        "id": "boundary:do_not_train_what_tools_can_observe",
        "kind": "capacity_contract",
        "name": "do_not_train_what_tools_can_observe",
        "role": "weights learn when/how to use tools and interpret observations; tools/retrieval store observable facts and long-tail details",
        "status": "active_contract",
    },
    {
        "id": "signal:verifier_reward_value_grounding",
        "kind": "supervision_signal",
        "name": "verifier_reward_value_grounding",
        "role": "compiler, tests, linters, static analyzers, dependency resolvers, stack traces, and CI produce objective labels for action usefulness and repair quality",
        "status": "required_signal",
    },
    {
        "id": "dataset_split:research_transfer_records",
        "kind": "dataset_split",
        "name": "research_transfer_records",
        "role": "paper/API/framework novelty converted into executable software transitions rather than raw text memorization",
        "status": "missing_or_future_manifest",
    },
]

EVOLUTION_EDGES = [
    ("model_role:100m_transition_kernel", "materializes_as", "policy_state:static_checkpoint_policy"),
    ("policy_state:static_checkpoint_policy", "is_updated_by", "loop:evolving_verified_training_cycle"),
    ("loop:evolving_verified_training_cycle", "produces_next", "policy_state:static_checkpoint_policy"),
    ("loop:evolving_verified_training_cycle", "trains", "model_role:100m_transition_kernel"),
    ("loop:evolving_verified_training_cycle", "consumes", "dataset_object:verified_transition_record"),
    ("dataset_object:verified_transition_record", "supervises", "training_objective:transition_prediction"),
    ("dataset_object:verified_transition_record", "supervises", "training_objective:verified_repair_transition"),
    ("compiler_stage:raw_corpus_to_structured_operators", "emits", "dataset_object:verified_transition_record"),
    ("policy:knowledge_transfer_policy", "uses", "compiler_stage:research_to_transition_compiler"),
    ("compiler_stage:research_to_transition_compiler", "produces", "dataset_split:research_transfer_records"),
    ("dataset_split:research_transfer_records", "feeds", "dataset_object:verified_transition_record"),
    ("paper_modality:research_operator_card", "is_compiled_by", "compiler_stage:research_to_transition_compiler"),
    ("operator:software_action_transition_algebra", "is_learned_by", "model_role:100m_transition_kernel"),
    ("dataset_object:verified_transition_record", "contains", "operator:software_action_transition_algebra"),
    ("boundary:do_not_train_what_tools_can_observe", "governs", "model_role:100m_transition_kernel"),
    ("boundary:do_not_train_what_tools_can_observe", "routes_facts_to", "external_memory:retrieval_long_tail_facts"),
    ("signal:verifier_reward_value_grounding", "labels", "dataset_object:verified_transition_record"),
    ("architecture_layer:verifier_repair", "provides", "signal:verifier_reward_value_grounding"),
    ("support_module:source_inventory_lineage_tracker", "guards", "dataset_split:research_transfer_records"),
    ("support_module:structured_dataset_junk_ranker", "routes", "dataset_object:verified_transition_record"),
]

REQUIRED_EXISTING_SUPPORT = [
    "model_role:100m_transition_kernel",
    "training_objective:transition_prediction",
    "training_objective:verified_repair_transition",
    "compiler_stage:raw_corpus_to_structured_operators",
    "paper_modality:research_operator_card",
    "external_memory:retrieval_long_tail_facts",
    "architecture_layer:verifier_repair",
    "support_module:source_inventory_lineage_tracker",
    "support_module:structured_dataset_junk_ranker",
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if any(existing.get("id") == node["id"] for existing in nodes):
        return False
    nodes.append({**node, "authority": AUTHORITY_CLOSED, "recovered_from": NAME})
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    key = (source, relation, target)
    if any((edge.get("source"), edge.get("relation"), edge.get("target")) == key for edge in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def attach_policy_evolution(graph: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    nodes = list(graph.get("nodes") or [])
    edges = list(graph.get("edges") or [])
    existing_ids = {node.get("id") for node in nodes}
    missing_support = [node_id for node_id in REQUIRED_EXISTING_SUPPORT if node_id not in existing_ids]
    added_nodes = sum(1 for node in EVOLUTION_NODES if add_node(nodes, node))
    added_edges = sum(1 for source, relation, target in EVOLUTION_EDGES if add_edge(edges, source, relation, target))
    out = {"version": NAME, "nodes": nodes, "edges": edges}
    metrics = {
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "missing_existing_support_nodes": missing_support,
        "evolution_node_count": len(EVOLUTION_NODES),
        "evolution_edge_count": len(EVOLUTION_EDGES),
    }
    return out, metrics


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    out, attach = attach_policy_evolution(graph)
    failures: list[str] = []
    if not graph:
        failures.append("missing_base_graph")
    if attach["missing_existing_support_nodes"]:
        failures.append("missing_existing_support_nodes")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8897, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    graph_path = OUT_DIR / "central_research_graph_with_policy_evolution_knowledge_transfer.json"
    nodes_path = OUT_DIR / "central_research_graph_with_policy_evolution_knowledge_transfer_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_policy_evolution_knowledge_transfer_edges.jsonl"
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
        "decision": "Attached policy-evolution and knowledge-transfer thesis to central graph." if not failures else "Policy-evolution graph attachment failed.",
        "next_best_step": "Future curriculum work should compile novelty into verified transition records and keep observable facts in retrieval/tools; Stage8890 still requires explicit authorization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8898 Policy Evolution And Knowledge Transfer",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This attaches the second half of the transition-compression thesis: a checkpoint is static, but the full software-maintainer system evolves through verified failure mining, teacher traces, research-transfer records, and retraining cycles.",
        "",
        "Novel papers/APIs/framework behavior should not be memorized as raw text. They should be compiled into research-operator cards, implementation plans, tests, patch steps, verifier observations, and verified transition records.",
        "",
        "Hard contract: do not train the model to remember what tools can observe. Weights learn transition policy; retrieval/tools/verifiers store facts and provide grounding.",
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
    marker = "## Stage8898 Policy Evolution And Knowledge Transfer"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8898 records that the 100M checkpoint is static at inference but evolves through the surrounding verified training loop. The model should learn transition operators, while retrieval/tools/verifiers retain observable long-tail facts.",
            "",
            "It also adds the knowledge-transfer policy: unfamiliar papers/APIs/framework details must be compiled into research-operator cards, tests, implementation plans, patch steps, verifier observations, and verified transition records before they create gradients.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
