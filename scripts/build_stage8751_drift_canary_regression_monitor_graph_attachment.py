#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8751
NAME = "stage8751_drift_canary_regression_monitor_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8749_golden_locked_eval_suite_graph_attachment/central_research_graph_with_golden_locked_eval_suite.json"
SOURCE = ROOT / "runs/summaries/stage8750_drift_canary_regression_monitor_readiness.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DRIFT_CANARY_REGRESSION_MONITOR_GRAPH_ATTACHMENT_STAGE8751.md"
BACKUP_ROOT = Path("/arxiv/agentkernel_recovery/stage8750_8751_drift_canary_regression_monitor")
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}


def add_node(nodes: dict, node: dict) -> int:
    node_id = node["id"]
    if node_id in nodes:
        nodes[node_id].update(node)
        return 0
    nodes[node_id] = node
    return 1


def add_edge(edges: list, src: str, relation: str, dst: str) -> None:
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": NAME}
    if edge not in edges:
        edges.append(edge)


def write_registry(card: dict) -> None:
    path = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
    registry = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"passed": True, "rows": []}
    rows = [row for row in registry.get("rows", []) if int(row.get("stage", -1)) != STAGE]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: int(row.get("stage", -1)))
    registry["rows"] = rows
    registry["passed"] = all(row.get("passed") is True for row in rows)
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def backup(paths: list[Path]) -> int:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in paths:
        if src.exists():
            dst = BACKUP_ROOT / src.relative_to(ROOT)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    return copied


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    module = "support_module:drift_canary_regression_monitor"
    added = add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "drift_canary_regression_monitor", "status": "ready_promotion_blocking_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED})
    reasons = ["regression_drop_exceeded", "below_min_score", "locked_eval_leakage", "contamination_detected", "missing_metric_card"]
    for reason in reasons:
        rid = f"promotion_block_reason:{reason}"
        added += add_node(nodes, {"id": rid, "kind": "promotion_block_reason", "node_type": "promotion_block_reason", "status": "active_gate", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "may_emit", rid)
    for upstream in ["support_module:golden_locked_eval_suite", "support_module:contamination_leakage_detector", "support_module:training_telemetry_metrics", "support_module:dataset_cartography_active_learning"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:stage_registry_authority_gate", "objective:bounded_decoder_ce"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "blocks_or_allows", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_drift_canary_regression_monitor.json"
    nodes_path = OUT_DIR / "central_research_graph_with_drift_canary_regression_monitor_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_drift_canary_regression_monitor_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "stage_name": NAME, "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "promotion_block_reasons_attached": len(reasons), "added_nodes": added, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"])}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "backup_root": str(BACKUP_ROOT)}, "decision": "Attached drift canary regression monitor as promotion-blocking governance for old-skill preservation.", "next_best_step": "Run a support-stack integration audit over source lineage, provenance, contamination, locked eval, canaries, and curriculum compiler.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8751 Drift Canary Regression Monitor Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached canary/regression promotion-blocking gates to central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    card["metrics"]["backup_files_copied"] = backup([ROOT / "scripts/drift_canary_regression_monitor.py", ROOT / "tests/test_drift_canary_regression_monitor.py", SOURCE, SUMMARY, DOC, graph_path, nodes_path, edges_path])
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    backup([SUMMARY, DOC])
    write_registry(card)
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
