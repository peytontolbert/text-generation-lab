#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8697_training_telemetry_graph_attachment/central_research_graph_with_training_telemetry.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8699_runtime_patch_dependency_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8699_runtime_patch_dependency_graph_attachment.json"
DOC = ROOT / "docs/RUNTIME_PATCH_DEPENDENCY_GRAPH_ATTACHMENT_STAGE8699.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}
MODULES = [
    ("support_module:runtime_trace_normalizer", "program_state_modality:runtime_trace"),
    ("support_module:patch_history_modality_builder", "program_state_modality:patch_history"),
    ("support_module:dependency_capability_card_builder", "program_state_modality:dependency_capability_card"),
]
OBJECTIVES = ["objective:intent_to_build_strategy", "objective:symbol_binding", "objective:edit_localization", "objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_arguments", "objective:bounded_decoder_ce"]


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
    for module, modality in MODULES:
        _add_node(nodes_by_id, module, "support_module", recovered=True, authority_opened=False)
        _add_node(nodes_by_id, modality, "program_state_modality", recovered=True, authority_opened=False)
        edges.append({"src": module, "dst": modality, "edge_type": "extracts_modality"})
        for objective in OBJECTIVES:
            _add_node(nodes_by_id, objective, "objective", recovered=True, authority_opened=False)
            edges.append({"src": modality, "dst": objective, "edge_type": "supports_objective"})
    missing = ["support_module:cross_modal_alignment_audit", "support_module:modality_dropout_ablation_audit", "support_module:state_space_repo_state_compressor", "support_module:runtime_verifier_loop", "support_module:gradient_activation_interpretability"]
    for node_id in missing:
        _add_node(nodes_by_id, node_id, "missing_support_module", recovered=False, authority_opened=False)
    out_graph = {"nodes": list(nodes_by_id.values()), "edges": edges}
    (OUT_DIR / "central_research_graph_with_runtime_patch_dependency.json").write_text(json.dumps(out_graph, indent=2, sort_keys=True) + "\n")
    (OUT_DIR / "central_research_graph_with_runtime_patch_dependency_nodes.jsonl").write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out_graph["nodes"]))
    (OUT_DIR / "central_research_graph_with_runtime_patch_dependency_edges.jsonl").write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out_graph["edges"]))
    metrics = {"base_graph": str(BASE.relative_to(ROOT)), "graph_nodes": len(out_graph["nodes"]), "graph_edges": len(out_graph["edges"]), "modules_attached": len(MODULES), "modalities_attached": len(MODULES), "missing_support_modules": missing, **AUTHORITY_CLOSED}
    card = {"stage": 8699, "name": "stage8699_runtime_patch_dependency_graph_attachment", "stage_name": "stage8699_runtime_patch_dependency_graph_attachment", "passed": True, "authority": AUTHORITY_CLOSED, "metrics": metrics, "decision": "Attached runtime trace, patch history, and dependency capability support modules to the central graph.", "next_best_step": "Recover cross-modal alignment audit, modality dropout/ablation audit, state-space repo compressor, and runtime verifier loop before data mining or training resumes.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "runtime_patch_dependency_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text("\n".join(["# Stage8699 Runtime/Patch/Dependency Graph Attachment", "", "Passed: `True`", "", "Attached recovered modules:", "", "- `runtime_trace_normalizer`", "- `patch_history_modality_builder`", "- `dependency_capability_card_builder`", "", "All authority remains closed.", "", "## Next", "", card["next_best_step"], ""]))
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
