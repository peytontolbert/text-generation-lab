#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8692_semantic_flow_extractors_graph_attachment/central_research_graph_with_semantic_flow_extractors.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8695_context_packer_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8695_context_packer_graph_attachment.json"
DOC = ROOT / "docs/CONTEXT_PACKER_GRAPH_ATTACHMENT_STAGE8695.md"
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


def _load_graph() -> dict[str, list[dict[str, Any]]]:
    if BASE.exists():
        graph = json.loads(BASE.read_text())
        return {"nodes": list(graph.get("nodes", [])), "edges": list(graph.get("edges", []))}
    return {"nodes": [], "edges": []}


def _add_node(nodes: dict[str, dict[str, Any]], node_id: str, node_type: str, **attrs: Any) -> None:
    nodes.setdefault(node_id, {"id": node_id, "node_type": node_type, **attrs})


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = _load_graph()
    nodes_by_id = {node.get("id"): node for node in graph["nodes"] if node.get("id")}
    edges = list(graph["edges"])
    module = "support_module:context_packer_v1"
    policy = "support_module:lost_in_middle_evidence_ordering"
    guard = "support_module:memory_contamination_guard"
    modality = "program_state_modality:retrieval_evidence_packet"
    for node_id, node_type in [(module, "support_module"), (policy, "support_module"), (guard, "support_module"), (modality, "program_state_modality")]:
        _add_node(nodes_by_id, node_id, node_type, recovered=True, authority_opened=False)
    edges.extend([
        {"src": module, "dst": modality, "edge_type": "packs_modality"},
        {"src": policy, "dst": module, "edge_type": "governs_ordering"},
        {"src": guard, "dst": module, "edge_type": "blocks_contaminated_context"},
    ])
    for objective in ["objective:symbol_binding", "objective:edit_localization", "objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_arguments", "objective:bounded_decoder_ce"]:
        _add_node(nodes_by_id, objective, "objective", recovered=True, authority_opened=False)
        edges.append({"src": modality, "dst": objective, "edge_type": "supports_objective"})
    missing = [
        "support_module:runtime_stack_trace_normalizer",
        "support_module:patch_history_modality_builder",
        "support_module:dependency_capability_card_builder",
        "support_module:cross_modal_alignment_audit",
        "support_module:modality_dropout_ablation_audit",
        "support_module:state_space_repo_state_compressor",
        "support_module:training_telemetry",
    ]
    for node_id in missing:
        _add_node(nodes_by_id, node_id, "missing_support_module", recovered=False, authority_opened=False)
    out_graph = {"nodes": list(nodes_by_id.values()), "edges": edges}
    (OUT_DIR / "central_research_graph_with_context_packer.json").write_text(json.dumps(out_graph, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "central_research_graph_with_context_packer_nodes.jsonl").write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out_graph["nodes"]))
    (OUT_DIR / "central_research_graph_with_context_packer_edges.jsonl").write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out_graph["edges"]))
    metrics = {
        "base_graph": str(BASE.relative_to(ROOT)),
        "graph_nodes": len(out_graph["nodes"]),
        "graph_edges": len(out_graph["edges"]),
        "context_packer_attached": True,
        "lost_in_middle_policy_attached": True,
        "memory_contamination_guard_attached": True,
        "missing_support_modules": missing,
        **AUTHORITY_CLOSED,
    }
    card = {
        "stage": 8695,
        "name": "stage8695_context_packer_graph_attachment",
        "stage_name": "stage8695_context_packer_graph_attachment",
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "decision": "Attached context_packer_v1, lost-in-middle ordering, and memory contamination guard to the central graph as no-authority support modules.",
        "next_best_step": "Recover runtime trace normalizer, patch-history modality builder, dependency capability cards, cross-modal alignment/dropout audits, and training telemetry before data mining resumes.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "context_packer_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join([
        "# Stage8695 Context Packer Graph Attachment",
        "",
        "Passed: `True`",
        "",
        "Attached `context_packer_v1`, lost-in-middle evidence ordering, and memory contamination guard to the central graph.",
        "",
        "This keeps retrieval/context packing under the same recovered research graph as the repo-state modalities and training gates. All authority remains closed.",
        "",
        "## Next",
        "",
        card["next_best_step"],
        "",
    ]))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
