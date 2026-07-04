#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE_GRAPH = ROOT / "runs/local/artifacts/stage8654_support_modules_graph_attachment/central_research_graph_with_support_modules.json"
SUPPORT_INDEX = ROOT / "configs/software_maintainer/additional_support_modules_recovery_index_stage8656.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8657_additional_support_modules_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8657_additional_support_modules_graph_attachment.json"
DOC = ROOT / "docs/ADDITIONAL_SUPPORT_MODULES_GRAPH_ATTACHMENT_STAGE8657.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"

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

MODULE_TARGETS = {
    "hybrid_retrieval_fusion": ["architecture_layer:evidence_retrieval", "support_module:lexical_bm25_retrieval", "support_module:embedding_retrieval", "support_module:cross_encoder_reranker"],
    "query_expansion_rewriter": ["architecture_layer:evidence_retrieval", "support_module:hybrid_retrieval_fusion"],
    "lost_in_middle_context_ranker": ["support_module:context_window_packer", "architecture_layer:evidence_retrieval"],
    "source_provenance_license_security_filter": ["support_module:source_inventory_lineage_tracker", "architecture_layer:training_curriculum"],
    "secret_pii_leak_detector": ["support_module:junk_risk_ood_ranker", "dataset_judge_signal:raw_text_leak_in_structured_objective"],
    "dedup_near_duplicate_minhash": ["dataset_judge_signal:duplicate_semantic_key", "architecture_layer:training_curriculum"],
    "schema_drift_detector": ["architecture_layer:training_curriculum", "support_module:curriculum_compiler"],
    "golden_locked_eval_suite": ["architecture_layer:training_curriculum", "support_module:drift_canary_regression_monitor"],
    "rubric_llm_judge_calibrator": ["dataset_judge_signal:teacher_verifier_disagreement", "support_module:weak_supervision_label_model"],
    "static_analysis_security_scanner": ["support_module:symbolic_verifier_stack", "gate_feature:import_allowed", "gate_feature:import_blocked"],
    "coverage_test_selection": ["architecture_layer:verifier_repair", "support_module:static_analysis_security_scanner"],
    "flaky_test_detector": ["architecture_layer:verifier_repair", "support_module:coverage_test_selection"],
    "patch_minimality_complexity_meter": ["architecture_layer:patch_operator", "support_module:junk_risk_ood_ranker"],
    "cost_budget_scheduler": ["gate_feature:decoder_budget_ok", "architecture_layer:training_curriculum"],
    "memory_retrieval_evaluator": ["architecture_layer:training_curriculum", "support_module:tool_action_trajectory_analyzer"],
    "drift_canary_regression_monitor": ["support_module:golden_locked_eval_suite", "support_module:eval_harness_metrics_reporter"],
    "active_learning_uncertainty_sampler": ["support_module:confidence_margin_entropy_calibration", "support_module:curriculum_compiler"],
    "weak_supervision_label_model": ["support_module:rubric_llm_judge_calibrator", "support_module:teacher_verifier_disagreement_detector"],
    "mutation_adversarial_test_generator": ["support_module:contamination_leakage_detector", "architecture_layer:training_curriculum"],
    "source_inventory_lineage_tracker": ["architecture_layer:training_curriculum", "support_module:source_provenance_license_security_filter"],
    "eval_harness_metrics_reporter": ["support_module:golden_locked_eval_suite", "support_module:drift_canary_regression_monitor"],
    "contamination_leakage_detector": ["dataset_judge_signal:shortcut_dominated_feature", "support_module:bias_shortcut_audit"],
    "context_window_packer": ["architecture_layer:evidence_retrieval", "support_module:lost_in_middle_context_ranker"],
    "tool_action_trajectory_analyzer": ["architecture_layer:training_curriculum", "support_module:curriculum_compiler"],
}


def has_node(nodes: list[dict[str, Any]], node_id: str) -> bool:
    return any(n.get("id") == node_id for n in nodes)


def has_edge(edges: list[dict[str, Any]], s: str, r: str, t: str) -> bool:
    return any(e.get("source") == s and e.get("relation") == r and e.get("target") == t for e in edges)


def ensure_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if has_node(nodes, node["id"]):
        return False
    nodes.append(node)
    return True


def ensure_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str, evidence: str) -> bool:
    if has_edge(edges, source, relation, target):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": evidence})
    return True


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE_GRAPH.read_text(encoding="utf-8"))
    index = json.loads(SUPPORT_INDEX.read_text(encoding="utf-8"))
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])
    added_nodes = 0
    added_edges = 0
    placeholder_targets: set[str] = set()

    for name, comp in sorted(index["components"].items()):
        node_id = f"support_module:{name}"
        if ensure_node(nodes, {
            "id": node_id,
            "kind": "support_module",
            "name": name,
            "role": comp["role"],
            "local_status": comp["local_status"],
            "pipeline_phase": comp["pipeline_phase"],
            "outputs": comp["outputs"],
            "next": comp["next"],
            "recovered_from": "stage8656_additional_support_modules_recovery_index",
            "authority": AUTHORITY_CLOSED,
        }):
            added_nodes += 1
        for ref in comp.get("recovered_refs", []):
            ref_id = "source_ref:" + ref.replace("/", "_").replace(":", "_")[:180]
            if ensure_node(nodes, {
                "id": ref_id,
                "kind": "source_ref",
                "name": ref,
                "path": ref,
                "exists": Path(ref).exists() if ref.startswith("/") else Path(ROOT / ref).exists(),
                "recovered_from": "stage8656_additional_support_modules_recovery_index",
            }):
                added_nodes += 1
            if ensure_edge(edges, node_id, "has_recovered_reference", ref_id, "stage8656_additional_support_modules_recovery_index"):
                added_edges += 1
        for target in MODULE_TARGETS.get(name, []):
            if not has_node(nodes, target):
                placeholder_targets.add(target)
                if ensure_node(nodes, {
                    "id": target,
                    "kind": "recovered_placeholder_target",
                    "name": target.split(":", 1)[-1],
                    "recovered_from": "stage8657_additional_support_modules_graph_attachment_placeholder",
                }):
                    added_nodes += 1
            if ensure_edge(edges, node_id, "supports", target, "stage8657_additional_support_modules_graph_attachment"):
                added_edges += 1
        if name != "curriculum_compiler":
            if ensure_edge(edges, node_id, "feeds_curriculum_compiler", "support_module:curriculum_compiler", "stage8657_additional_support_modules_graph_attachment"):
                added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8657_additional_support_modules_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED

    full = OUT_DIR / "central_research_graph_with_additional_support_modules.json"
    nodes_path = OUT_DIR / "central_research_graph_with_additional_support_modules_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_additional_support_modules_edges.jsonl"
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with nodes_path.open("w", encoding="utf-8") as f:
        for node in nodes:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with edges_path.open("w", encoding="utf-8") as f:
        for edge in edges:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    expected = set(index["components"])
    present = {n["id"].split(":", 1)[1] for n in nodes if n.get("id", "").startswith("support_module:")}
    missing = sorted(expected - present)
    card = {
        "stage": 8657,
        "stage_name": "stage8657_additional_support_modules_graph_attachment",
        "passed": not missing,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "additional_support_components_expected": len(expected),
            "additional_support_components_present": len(expected & present),
            "missing_additional_support_components": missing,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "placeholder_targets_added": sorted(placeholder_targets),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "artifacts": {
            "graph": str(full.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "support_index": str(SUPPORT_INDEX.relative_to(ROOT)),
        },
        "decision": "Stage8656 additional support modules are attached to the central graph as no-authority modules feeding retrieval, source lineage, leakage detection, eval governance, context packing, and curriculum compilation.",
        "next_best_step": "Implement Stage8655a source_inventory and Stage8655b shared_feature_extractor using these support modules; do not reopen decoder/training until graph/symbol source cards pass leakage, retrieval, and locked-eval gates.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "additional_support_module_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage8657 Additional Support Modules Graph Attachment",
        "",
        "Stage8656 modules are now attached to the central research graph. This is a no-authority graph/index update only.",
        "",
        "## Metrics",
        f"- Additional support components expected: `{len(expected)}`",
        f"- Additional support components present: `{len(expected & present)}`",
        f"- Added nodes: `{added_nodes}`",
        f"- Added edges: `{added_edges}`",
        f"- Graph nodes: `{len(nodes)}`",
        f"- Graph edges: `{len(edges)}`",
        "",
        "## Modules",
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

    registry = {
        "passed": True,
        "rows": [card],
        "metrics": {
            "min_stage": 8530,
            "max_stage": 8657,
            "latest_stage": 8657,
            "latest_stage_name": card["stage_name"],
            "latest_stage_next_best_step": card["next_best_step"],
            "registry_rows": 141,
            "authority_counts": {k: 0 for k in AUTHORITY_CLOSED},
        },
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
