#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8790
NAME = "stage8790_source_backed_verifier_repair_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8787_traced_eval_graph_attachment/central_research_graph_with_traced_eval.json"
SOURCES = [
    ROOT / "runs/summaries/stage8788_source_backed_verifier_repair_candidate_manifest.json",
    ROOT / "runs/summaries/stage8789_source_backed_verifier_repair_candidate_audit.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_VERIFIER_REPAIR_GRAPH_ATTACHMENT_STAGE8790.md"
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
    audit = summaries[1]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))

    objective = "objective:source_backed_verifier_repair"
    builder = "builder:source_backed_verifier_repair"
    added_nodes = 0
    added_nodes += int(add_node(nodes, {
        "id": objective,
        "kind": "objective",
        "node_type": "objective",
        "name": "source_backed_verifier_repair",
        "status": "candidate_audit_passed_no_training",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "rows": audit.get("metrics", {}).get("rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": builder,
        "kind": "builder",
        "node_type": "builder",
        "name": "source_backed_verifier_repair_builder",
        "status": "recovered_candidate_builder",
        "summary": str(SOURCES[0].relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    for upstream in [
        "objective:source_backed_patch_operator",
        "support_module:traced_eval_observability",
        "support_module:static_analysis_security_scanner",
        "support_module:cost_budget_scheduler",
        "support_module:dataset_junk_ood_ranker_v1",
        "support_module:curriculum_compiler",
    ]:
        add_node(nodes, {"id": upstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "supports", objective)
    add_edge(edges, builder, "builds", objective)
    add_edge(edges, objective, "precedes", "objective:bounded_decoder_arguments")
    add_edge(edges, objective, "feeds_failure_repair_loop_for", "objective:denoise_repair")

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_source_backed_verifier_repair.json"
    nodes_path = OUT_DIR / "central_research_graph_with_source_backed_verifier_repair_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_source_backed_verifier_repair_edges.jsonl"
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
        "decision": "Attached source-backed verifier-repair candidate objective to the central graph as no-training candidate support for bounded decoder arguments and denoise repair." if not failures else "Source-backed verifier-repair graph attachment failed.",
        "next_best_step": "Recover bounded decoder argument candidate controls under gate_status_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "source_backed_verifier_repair_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8790 Source-Backed Verifier Repair Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached source-backed verifier-repair candidate objective to the central graph.", "", "Authority remains closed: no training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
