#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_GRAPH = ROOT / "runs/local/artifacts/stage8628_useful_recovery_integration/central_research_graph_with_useful_recoveries.json"
SUPPORT_INDEX = ROOT / "configs/software_maintainer/support_systems_recovery_index_stage8653.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8654_support_modules_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8654_support_modules_graph_attachment.json"
DOC = ROOT / "docs/SUPPORT_MODULES_GRAPH_ATTACHMENT_STAGE8654.md"

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

SUPPORT_TO_TARGETS = {
    "lexical_bm25_retrieval": ["architecture_layer:evidence_retrieval", "recovery_target:evidence_retrieval", "architecture_layer:repo_state_graph_v1"],
    "embedding_retrieval": ["architecture_layer:evidence_retrieval", "fusion_input:retrieval_evidence_confidence"],
    "cross_encoder_reranker": ["architecture_layer:evidence_retrieval", "fusion_input:retrieval_evidence_confidence"],
    "feature_detectors_static": ["dataset_judge_signal:shortcut_dominated_feature", "gate_feature:junk_ranker_reason_bits"],
    "ngram_repetition_style_detectors": ["gate_feature:junk_ranker_reason_bits", "dataset_judge_signal:degenerate_repetition_target"],
    "junk_risk_ood_ranker": ["gate_feature:junk_ranker_route", "fusion_input:junk_ranker_route"],
    "cluster_slice_detection": ["recovery_target:scale_judged_curriculum", "dataset_judge_signal:duplicate_semantic_key"],
    "bias_shortcut_audit": ["dataset_judge_signal:shortcut_dominated_feature", "recovery_target:scale_judged_curriculum"],
    "dataset_cartography_dynamics": ["architecture_layer:training_curriculum", "recovery_target:scale_judged_curriculum"],
    "training_data_attribution": ["architecture_layer:training_curriculum", "recovery_target:scale_judged_curriculum"],
    "confidence_margin_entropy_calibration": ["model_family:bayesian_calibration", "fusion_input:calibrated_confidence"],
    "symbolic_verifier_stack": ["model_family:symbolic_verifiers", "fusion_input:verifier_result", "architecture_layer:verifier_repair"],
    "curriculum_compiler": ["architecture_layer:training_curriculum", "recovery_target:scale_judged_curriculum"],
    "reservoir_source_sampler": ["recovery_target:scale_judged_curriculum", "architecture_layer:training_curriculum"],
    "teacher_verifier_disagreement_detector": ["dataset_judge_signal:teacher_verifier_disagreement", "architecture_layer:verifier_repair"],
}


def node_exists(nodes: list[dict[str, Any]], node_id: str) -> bool:
    return any(node.get("id") == node_id for node in nodes)


def edge_exists(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    return any(edge.get("source") == source and edge.get("relation") == relation and edge.get("target") == target for edge in edges)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE_GRAPH.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT_INDEX.read_text(encoding="utf-8"))
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])

    added_nodes = 0
    added_edges = 0
    missing_targets: dict[str, list[str]] = {}

    for name, comp in sorted(support["components"].items()):
        node_id = f"support_module:{name}"
        if not node_exists(nodes, node_id):
            nodes.append({
                "id": node_id,
                "kind": "support_module",
                "name": name,
                "role": comp["role"],
                "local_status": comp["local_status"],
                "pipeline_phase": comp["pipeline_phase"],
                "outputs": comp["outputs"],
                "next": comp["next"],
                "recovered_from": "stage8653_support_systems_recovery_index",
                "authority": AUTHORITY_CLOSED,
            })
            added_nodes += 1
        for ref in comp.get("recovered_refs", []):
            ref_id = "source_ref:" + ref.replace("/", "_").replace(":", "_")[:180]
            if not node_exists(nodes, ref_id):
                nodes.append({
                    "id": ref_id,
                    "kind": "source_ref",
                    "name": ref,
                    "path": ref,
                    "exists": Path(ref).exists(),
                    "recovered_from": "stage8653_support_systems_recovery_index",
                })
                added_nodes += 1
            if not edge_exists(edges, node_id, "has_recovered_reference", ref_id):
                edges.append({
                    "source": node_id,
                    "relation": "has_recovered_reference",
                    "target": ref_id,
                    "evidence_source": "stage8653_support_systems_recovery_index",
                })
                added_edges += 1
        targets = SUPPORT_TO_TARGETS.get(name, [])
        for target in targets:
            if not node_exists(nodes, target):
                missing_targets.setdefault(name, []).append(target)
                if not node_exists(nodes, target):
                    nodes.append({
                        "id": target,
                        "kind": "recovered_placeholder_target",
                        "name": target.split(":", 1)[-1],
                        "recovered_from": "stage8654_support_modules_graph_attachment_placeholder",
                    })
                    added_nodes += 1
            if not edge_exists(edges, node_id, "supports", target):
                edges.append({
                    "source": node_id,
                    "relation": "supports",
                    "target": target,
                    "evidence_source": "stage8654_support_modules_graph_attachment",
                })
                added_edges += 1
        if not edge_exists(edges, node_id, "feeds_curriculum_compiler", "support_module:curriculum_compiler") and name != "curriculum_compiler":
            edges.append({
                "source": node_id,
                "relation": "feeds_curriculum_compiler",
                "target": "support_module:curriculum_compiler",
                "evidence_source": "stage8654_support_modules_graph_attachment",
            })
            added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8654_support_modules_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED

    full_path = OUT_DIR / "central_research_graph_with_support_modules.json"
    nodes_path = OUT_DIR / "central_research_graph_with_support_modules_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_support_modules_edges.jsonl"
    full_path.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with nodes_path.open("w", encoding="utf-8") as f:
        for node in nodes:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with edges_path.open("w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    support_nodes = [node for node in nodes if node.get("kind") == "support_module"]
    expected = set(support["components"])
    present = {node["id"].split(":", 1)[1] for node in support_nodes if node["id"].startswith("support_module:")}
    missing_support = sorted(expected - present)
    card = {
        "stage": 8654,
        "stage_name": "stage8654_support_modules_graph_attachment",
        "passed": not missing_support,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "support_components_expected": len(expected),
            "support_components_present": len(present & expected),
            "missing_support_components": missing_support,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "missing_existing_targets_patched_as_placeholders": missing_targets,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "artifacts": {
            "graph": str(full_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "support_index": str(SUPPORT_INDEX.relative_to(ROOT)),
        },
        "decision": "Stage8653 support modules are now attached to the central research graph as no-authority support_module nodes with recovered references and compiler/fusion/judge edges.",
        "next_best_step": "Use the attached support modules to build source-backed graph/symbol-binding recovery cards with BM25/dense retrieval baselines, shared feature extraction, and junk/risk/OOD ranker gates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "support_module_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Stage8654 Support Modules Graph Attachment",
        "",
        "Stage8653 support systems are now explicit central-graph nodes. This is no-authority documentation/configuration only.",
        "",
        "## Metrics",
        f"- Support components expected: `{len(expected)}`",
        f"- Support components present: `{len(present & expected)}`",
        f"- Added nodes: `{added_nodes}`",
        f"- Added edges: `{added_edges}`",
        f"- Graph nodes: `{len(nodes)}`",
        f"- Graph edges: `{len(edges)}`",
        "",
        "## Attached Support Modules",
    ]
    for name in sorted(expected):
        lines.append(f"- `support_module:{name}`")
    lines.extend([
        "",
        "## Authority Boundary",
        "- Model execution: closed",
        "- Decoder CE: closed",
        "- Denoise CE: closed",
        "- Runtime/source/body/Gemma/harness/scoring/promotion: closed",
        "",
        "## Next Step",
        card["next_best_step"],
    ])
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
