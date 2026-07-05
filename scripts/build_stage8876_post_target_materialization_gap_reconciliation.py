#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8876
NAME = "stage8876_post_target_materialization_gap_reconciliation"
BASE = ROOT / "runs/local/artifacts/stage8874_verifier_guided_repair_target_materialization_graph_attachment/central_research_graph_with_verifier_guided_repair_target_materialization.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "POST_TARGET_MATERIALIZATION_GAP_RECONCILIATION_STAGE8876.md"
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
RESOLUTION_MAP = {
    "gap:bounded_decoder_eval_strict_unique_target_materialization": "stage8820_heldout_non_ce_decoder_eval_design_manifest",
    "objective:eval_strict_unique_target_materialization": "stage8822_registry_spine_reconciliation_after_heldout_non_ce_eval_design",
    "objective:future_model_output_packet_schema": "stage8823_model_output_packet_telemetry_contract_manifest",
    "objective:future_probe_packet_readiness_audit": "stage8826_model_output_packet_readiness_contract_audit",
    "objective:future_model_output_capture_runner_design": "stage8837_model_output_capture_runner_static_design",
}
STATUS_BY_NODE = {
    "gap:bounded_decoder_eval_strict_unique_target_materialization": "resolved_by_heldout_non_ce_eval_design",
    "objective:eval_strict_unique_target_materialization": "resolved_by_heldout_non_ce_eval_design",
    "objective:future_model_output_packet_schema": "resolved_by_packet_telemetry_contract",
    "objective:future_probe_packet_readiness_audit": "resolved_by_packet_readiness_audit",
    "objective:future_model_output_capture_runner_design": "resolved_by_runner_static_design",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    registry = load(REGISTRY)
    passed_stage_names = {row.get("stage_name") for row in registry.get("rows", []) if row.get("passed") is True}
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    by_id = {node.get("id"): node for node in nodes}
    patched = []
    skipped = []
    for node_id, stage_name in RESOLUTION_MAP.items():
        node = by_id.get(node_id)
        if not node:
            skipped.append({"id": node_id, "reason": "missing_node", "resolved_by_stage": stage_name})
            continue
        if stage_name not in passed_stage_names:
            skipped.append({"id": node_id, "reason": "stage_not_passed_or_not_indexed", "resolved_by_stage": stage_name})
            continue
        old_status = node.get("status")
        node["previous_status"] = old_status
        node["status"] = STATUS_BY_NODE[node_id]
        node["resolved_by_stage"] = stage_name
        node["reconciled_by_stage"] = NAME
        node["authority"] = AUTHORITY_CLOSED
        patched.append({"id": node_id, "old_status": old_status, "new_status": node["status"], "resolved_by_stage": stage_name})
    out = {"version": NAME, "nodes": nodes, "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_post_target_materialization_reconciled.json"
    nodes_path = OUT_DIR / "central_research_graph_post_target_materialization_reconciled_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_post_target_materialization_reconciled_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges), encoding="utf-8")
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "candidate_nodes": len(RESOLUTION_MAP),
        "patched_nodes": len(patched),
        "skipped_nodes": len(skipped),
        "training_authorized": False,
        "decoder_ce_authorized": False,
        "denoise_ce_authorized": False,
        "runtime_authorized_flag": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": len(patched) == len(RESOLUTION_MAP) and not skipped,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "patched_nodes": patched,
        "skipped_nodes": skipped,
        "decision": "Reconciled heldout eval, packet telemetry, packet readiness, and runner static design statuses after verifier-guided target recovery.",
        "next_best_step": "Run a fresh central graph gap walk; expected remaining blockers should be true closed gates such as commit inventory preflight and CE/runtime execution authority.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "post_target_materialization_gap_reconciliation_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8876 Post Target Materialization Gap Reconciliation",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Patched nodes: `{metrics['patched_nodes']}`",
        f"Skipped nodes: `{metrics['skipped_nodes']}`",
        "",
        "Patched:",
        "",
        *[f"- `{item['id']}` -> `{item['resolved_by_stage']}`" for item in patched],
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
