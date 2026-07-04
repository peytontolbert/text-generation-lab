#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8678_symbol_binding_repair_graph_attachment/central_research_graph_with_symbol_binding_repair.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8681_program_state_multimodality_contract"
SUMMARY = ROOT / "runs/summaries/stage8681_program_state_multimodality_contract.json"
DOC = ROOT / "docs/PROGRAM_STATE_MULTIMODALITY_CONTRACT_STAGE8681.md"

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

MODALITIES = [
    "source_text",
    "cst_ast",
    "symbol_table",
    "import_export_graph",
    "dependency_graph",
    "type_signature_map",
    "call_graph",
    "data_flow_graph",
    "control_flow_graph",
    "compiler_ir",
    "docs_comments_readme",
    "tests_fixtures_ci",
    "runtime_stack_traces",
    "git_diffs_patch_history",
    "dependency_capability_cards",
]

IMPLEMENTATION_STATUS = {
    "recovered": [
        "repo_graph_node_edge_schema",
        "source_inventory_lineage",
        "shared_feature_normalizer",
        "source_backed_symbol_binding_seed",
        "retrieval_baselines",
        "locked_eval_packs",
        "leakage_shortcut_audits",
    ],
    "missing": [
        "ast_cst_extractor_card",
        "symbol_table_extractor_card",
        "import_dependency_graph_extractor_card",
        "type_signature_extractor_card",
        "call_graph_extractor_card",
        "data_flow_extractor_card",
        "control_flow_extractor_card",
        "dependency_capability_card_builder",
        "runtime_stack_trace_normalizer",
        "patch_history_modality_builder",
        "cross_modal_alignment_audit",
        "modality_dropout_ablation_audit",
    ],
}

OBJECTIVE_MODALITY_MAP = {
    "intent_to_build_strategy": ["source_text", "dependency_capability_cards", "import_export_graph"],
    "repo_state_graph_v1": ["symbol_table", "import_export_graph", "dependency_graph", "tests_fixtures_ci", "runtime_stack_traces"],
    "symbol_binding": ["symbol_table", "import_export_graph", "call_graph", "tests_fixtures_ci", "runtime_stack_traces"],
    "edit_localization": ["cst_ast", "symbol_table", "call_graph", "tests_fixtures_ci", "runtime_stack_traces"],
    "patch_operator": ["cst_ast", "type_signature_map", "control_flow_graph", "data_flow_graph", "dependency_graph"],
    "verifier_repair": ["tests_fixtures_ci", "runtime_stack_traces", "git_diffs_patch_history"],
    "bounded_decoder_arguments": ["source_text", "cst_ast", "symbol_table", "patch_operator"],
    "output_repair_denoise": ["source_text", "runtime_stack_traces", "tests_fixtures_ci"],
}


def has_node(nodes: list[dict[str, Any]], node_id: str) -> bool:
    return any(node.get("id") == node_id for node in nodes)


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if has_node(nodes, node["id"]):
        return False
    nodes.append(node)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str, evidence: str) -> bool:
    if any(edge.get("source") == source and edge.get("relation") == relation and edge.get("target") == target for edge in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": evidence})
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text())
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])
    added_nodes = 0
    added_edges = 0

    root = "architecture_layer:program_state_multimodality"
    if add_node(
        nodes,
        {
            "id": root,
            "kind": "architecture_layer",
            "name": "program_state_multimodality",
            "role": "codebase as aligned tokenized executable state-space modalities",
            "authority": AUTHORITY_CLOSED,
            "status": "contract_recovered_no_execution",
            "doc": str(DOC.relative_to(ROOT)),
        },
    ):
        added_nodes += 1

    for modality in MODALITIES:
        node_id = f"program_state_modality:{modality}"
        if add_node(
            nodes,
            {
                "id": node_id,
                "kind": "program_state_modality",
                "name": modality,
                "authority": AUTHORITY_CLOSED,
                "status": "contract_only",
                "recovered_from": "stage8681_program_state_multimodality_contract",
            },
        ):
            added_nodes += 1
        if add_edge(edges, root, "has_modality", node_id, "stage8681_program_state_multimodality_contract"):
            added_edges += 1

    for objective, modalities in OBJECTIVE_MODALITY_MAP.items():
        objective_id = f"objective_family:{objective}"
        if not has_node(nodes, objective_id):
            if add_node(nodes, {"id": objective_id, "kind": "objective_family", "name": objective, "authority": AUTHORITY_CLOSED}):
                added_nodes += 1
        for modality in modalities:
            if add_edge(edges, f"program_state_modality:{modality}", "supports_objective", objective_id, "stage8681_program_state_multimodality_contract"):
                added_edges += 1

    for missing in IMPLEMENTATION_STATUS["missing"]:
        node_id = f"missing_module:{missing}"
        if add_node(
            nodes,
            {
                "id": node_id,
                "kind": "missing_module",
                "name": missing,
                "blocks": "program_state_multimodality_scaleup",
                "authority": AUTHORITY_CLOSED,
            },
        ):
            added_nodes += 1
        if add_edge(edges, root, "blocked_by_missing_module", node_id, "stage8681_program_state_multimodality_contract"):
            added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8681_program_state_multimodality_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED

    graph_path = OUT_DIR / "central_research_graph_with_program_state_multimodality.json"
    nodes_path = OUT_DIR / "central_research_graph_with_program_state_multimodality_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_program_state_multimodality_edges.jsonl"
    graph_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes))
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges))

    card = {
        "stage": 8681,
        "stage_name": "stage8681_program_state_multimodality_contract",
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "modalities": len(MODALITIES),
            "objective_families_mapped": len(OBJECTIVE_MODALITY_MAP),
            "recovered_components": len(IMPLEMENTATION_STATUS["recovered"]),
            "missing_extractor_or_alignment_modules": len(IMPLEMENTATION_STATUS["missing"]),
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "modalities": MODALITIES,
        "objective_modality_map": OBJECTIVE_MODALITY_MAP,
        "implementation_status": IMPLEMENTATION_STATUS,
        "artifacts": {
            "doc": str(DOC.relative_to(ROOT)),
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Recovered program-state multimodality as a central architecture contract. It is contract-only and blocks data scale-up until extractor/alignment modules are implemented.",
        "next_best_step": "Build AST/CST, symbol table, import/dependency, test/failure trace, and cross-modal alignment contracts before source-backed scale-up.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "program_state_multimodality_contract_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
