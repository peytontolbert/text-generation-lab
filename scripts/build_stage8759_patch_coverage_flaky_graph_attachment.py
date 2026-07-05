#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8759
NAME = "stage8759_patch_coverage_flaky_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8755_schema_drift_detector_graph_attachment/central_research_graph_with_schema_drift_detector.json"
SOURCES = {
    "patch_minimality_complexity_meter": ROOT / "runs/summaries/stage8756_patch_minimality_complexity_meter_readiness.json",
    "coverage_test_selection": ROOT / "runs/summaries/stage8757_coverage_test_selection_readiness.json",
    "flaky_test_detector": ROOT / "runs/summaries/stage8758_flaky_test_detector_readiness.json",
}
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PATCH_COVERAGE_FLAKY_GRAPH_ATTACHMENT_STAGE8759.md"
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
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": NAME}
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    source_cards = {key: json.loads(path.read_text(encoding="utf-8")) for key, path in SOURCES.items()}
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    modules = {
        "patch_minimality_complexity_meter": {
            "routes": ["PASS_PATCH_MINIMALITY", "HOLD_PATCH_REVIEW", "HOLD_PUBLIC_API_REVIEW", "BLOCK_OVERBROAD_PATCH"],
            "gates": ["gate:patch_minimality_limits_changed_lines", "gate:patch_minimality_limits_files_changed", "gate:patch_minimality_reviews_public_api", "gate:patch_minimality_blocks_new_dependency_risk"],
        },
        "coverage_test_selection": {
            "routes": ["PASS_TARGETED_TEST_SELECTION", "NEEDS_BROAD_TEST_DISCOVERY", "HOLD_NO_CHANGESET"],
            "gates": ["gate:coverage_selection_requires_changeset", "gate:coverage_selection_prefers_coverage_map", "gate:coverage_selection_reports_gap"],
        },
        "flaky_test_detector": {
            "routes": ["PASS_STABLE_FAILURE", "PASS_STABLE_PASS", "HOLD_FLAKY_FAILURE", "HOLD_UNSTABLE_FAILURE_SIGNATURE", "HOLD_NO_RERUN_EVIDENCE", "HOLD_INSUFFICIENT_RERUNS"],
            "gates": ["gate:flaky_detector_requires_rerun_evidence", "gate:flaky_detector_holds_pass_fail_mix", "gate:flaky_detector_holds_unstable_signature"],
        },
    }
    for module_name, spec in modules.items():
        module_id = f"support_module:{module_name}"
        source = source_cards[module_name]
        added_nodes += int(add_node(nodes, {"id": module_id, "kind": "support_module", "node_type": "support_module", "name": module_name, "status": "ready_partial_no_execution_gate", "summary": str(SOURCES[module_name].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
        for route in spec["routes"]:
            route_id = f"{module_name}_route:{route}"
            added_nodes += int(add_node(nodes, {"id": route_id, "kind": f"{module_name}_route", "node_type": "row_route", "status": "row_route", "authority": AUTHORITY_CLOSED}))
            add_edge(edges, module_id, "may_emit_route", route_id)
        for gate in spec["gates"]:
            added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
            add_edge(edges, gate, "guards", module_id)
        for downstream in ["objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_ce", "support_module:curriculum_compiler", "support_module:dataset_junk_ood_ranker_v1"]:
            add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
            add_edge(edges, module_id, "gates", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_patch_coverage_flaky.json"
    nodes_path = OUT_DIR / "central_research_graph_with_patch_coverage_flaky_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_patch_coverage_flaky_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    passed = all(card.get("passed") is True for card in source_cards.values())
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "modules_attached": len(modules), "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached patch minimality, coverage test selection, and flaky test detector gates to the central graph as no-execution verifier/patch governance modules.",
        "next_best_step": "Recover eval_trace_to_dataset_patch_loop, then update source-backed builders to emit full gate_status cards.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "patch_coverage_flaky_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8759 Patch Coverage Flaky Graph Attachment",
        "",
        f"Passed: `{passed}`",
        "",
        "Attached patch minimality, coverage/test selection, and flaky failure stability gates to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
