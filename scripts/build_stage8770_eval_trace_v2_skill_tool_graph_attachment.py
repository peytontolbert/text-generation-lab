#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8770
NAME = "stage8770_eval_trace_v2_skill_tool_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8767_source_backed_edit_localization_graph_attachment/central_research_graph_with_source_backed_edit_localization.json"
SOURCES = [
    ROOT / "runs/summaries/stage8768_eval_trace_to_dataset_patch_loop_v2_readiness.json",
    ROOT / "runs/summaries/stage8769_skill_tool_registry_readiness.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_TRACE_V2_SKILL_TOOL_GRAPH_ATTACHMENT_STAGE8770.md"
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
    eval_v2 = "support_module:eval_trace_to_dataset_patch_loop_v2"
    skill = "support_module:skill_tool_registry"
    added_nodes += int(add_node(nodes, {"id": eval_v2, "kind": "support_module", "node_type": "support_module", "name": "eval_trace_to_dataset_patch_loop_v2", "status": "ready_no_generation_dataset_patch_compiler", "summary": str(SOURCES[0].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {"id": skill, "kind": "support_module", "node_type": "support_module", "name": "skill_tool_registry", "status": "ready_no_execution_tool_permission_ontology", "summary": str(SOURCES[1].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    for downstream in ["support_module:curriculum_compiler", "support_module:dataset_junk_ood_ranker_v1", "support_module:eval_trace_to_dataset_patch_loop", "builder:source_backed_symbol_binding", "builder:source_backed_edit_localization", "builder:source_backed_patch_operator"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_builder", "node_type": "support_or_builder", "authority": AUTHORITY_CLOSED})
        add_edge(edges, eval_v2, "feeds_dataset_patch_control_for", downstream)
        add_edge(edges, skill, "provides_tool_permission_surface_for", downstream)
    for tool_class in ["read_only", "workspace_write", "runtime_execution", "network", "external_write", "destructive"]:
        node_id = f"tool_permission:{tool_class}"
        add_node(nodes, {"id": node_id, "kind": "tool_permission", "node_type": "tool_permission", "authority": AUTHORITY_CLOSED})
        add_edge(edges, skill, "classifies_permission", node_id)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_eval_trace_v2_skill_tool.json"
    nodes_path = OUT_DIR / "central_research_graph_with_eval_trace_v2_skill_tool_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_eval_trace_v2_skill_tool_edges.jsonl"
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
        "decision": "Attached eval-trace v2 dataset patch compiler and skill/tool registry to the central graph. Both are no-execution support modules." if not failures else "Eval-trace v2 / skill-tool graph attachment failed.",
        "next_best_step": "Recover source-backed patch operator builder under gate_status_contract, then ngram_repetition_style_detectors if still missing.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "eval_trace_v2_skill_tool_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8770 Eval Trace V2 Skill Tool Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached the no-generation eval-trace patch compiler and no-execution skill/tool registry to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
