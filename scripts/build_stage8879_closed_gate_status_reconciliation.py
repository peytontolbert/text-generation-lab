#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8879
NAME = "stage8879_closed_gate_status_reconciliation"
BASE = ROOT / "runs/local/artifacts/stage8876_post_target_materialization_gap_reconciliation/central_research_graph_post_target_materialization_reconciled.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLOSED_GATE_STATUS_RECONCILIATION_STAGE8879.md"
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
REQUIRED_PASSED = {
    "objective:bounded_decoder_ce": [
        "stage8803_closed_bounded_decoder_ce_package_gate_audit",
        "stage8807_source_backed_decoder_target_materialization_audit",
        "stage8822_registry_spine_reconciliation_after_heldout_non_ce_eval_design",
        "stage8862_native_probe_interpretability_artifact_contract",
    ],
    "objective:denoise_repair": [
        "stage8811_output_repair_denoise_controls_shortcut_gate",
        "stage8873_verifier_guided_repair_target_materialization_audit",
        "stage8731_denoise_diffusion_repair_contract_readiness",
    ],
}
NEW_STATUS = {
    "objective:bounded_decoder_ce": "closed_gate_recovered_awaiting_explicit_tiny_execution_authorization",
    "objective:denoise_repair": "closed_gate_recovered_awaiting_dedicated_no_execution_denoise_authorization_review",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> None:
    ids = {n.get("id") for n in nodes}
    if node["id"] not in ids:
        nodes.append(node)


def add_edge(edges: list[dict[str, Any]], edge: dict[str, Any]) -> None:
    key = (edge.get("source"), edge.get("relation"), edge.get("target"))
    if key not in {(e.get("source"), e.get("relation"), e.get("target")) for e in edges}:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    registry = load(REGISTRY)
    passed_names = {row.get("stage_name") for row in registry.get("rows", []) if row.get("passed") is True}
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    by_id = {node.get("id"): node for node in nodes}
    patched = []
    skipped = []
    for node_id, required in REQUIRED_PASSED.items():
        node = by_id.get(node_id)
        missing = [name for name in required if name not in passed_names]
        if node is None:
            skipped.append({"id": node_id, "reason": "missing_node"})
            continue
        if missing:
            skipped.append({"id": node_id, "reason": "missing_required_passed_stage", "missing": missing})
            continue
        old_status = node.get("status")
        node["previous_status"] = old_status
        node["status"] = NEW_STATUS[node_id]
        node["reconciled_by_stage"] = NAME
        node["required_passed_stages"] = required
        node["authority"] = AUTHORITY_CLOSED
        if node_id == "objective:bounded_decoder_ce":
            node["decoder_ce_eligible_now_rows"] = 0
            node["execution_authorized_now"] = False
        if node_id == "objective:denoise_repair":
            node["denoise_ce_eligible_now_rows"] = 0
            node["runtime_verifier_execution_eligible_now_rows"] = 0
        patched.append({"id": node_id, "old_status": old_status, "new_status": node["status"], "required_passed_stages": required})
    add_node(nodes, {"id": "stage:8879", "kind": "stage", "name": "8879", "stage_name": NAME, "passed": not skipped, "path": str(SUMMARY.relative_to(ROOT)), "authority": AUTHORITY_CLOSED})
    for item in patched:
        add_edge(edges, {"source": "stage:8879", "relation": "reconciles_closed_gate", "target": item["id"], "evidence_source": NAME})
    out = {"version": NAME, "nodes": nodes, "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_closed_gate_status_reconciliation.json"
    nodes_path = OUT_DIR / "central_research_graph_with_closed_gate_status_reconciliation_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_closed_gate_status_reconciliation_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges), encoding="utf-8")
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "candidate_nodes": len(REQUIRED_PASSED),
        "patched_nodes": len(patched),
        "skipped_nodes": len(skipped),
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "model_execution_authorized_now": False,
        "decoder_ce_authorized": False,
        "denoise_ce_authorized": False,
        "runtime_authorized_flag": False,
        "training_authorized": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not skipped and len(patched) == len(REQUIRED_PASSED),
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "patched_nodes": patched,
        "skipped_nodes": skipped,
        "decision": "Reconciled bounded decoder CE and denoise repair from stale prerequisite-pending statuses to closed gates with recovered controls. No execution or CE authority opened.",
        "next_best_step": "Run a fresh central graph gap walk; expected remaining missing node should be optional metadata-only commit inventory preflight unless explicitly requested.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "closed_gate_status_reconciliation_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8879 Closed Gate Status Reconciliation",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Patched nodes: `{metrics['patched_nodes']}`",
        f"Skipped nodes: `{metrics['skipped_nodes']}`",
        "",
        "Patched:",
        "",
        *[f"- `{item['id']}` -> `{item['new_status']}`" for item in patched],
        "",
        "This opens no authority. Decoder CE, denoise CE, model execution, runtime, source/body emission, Gemma, harness, scoring, controller merge, mining, and promotion remain closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
