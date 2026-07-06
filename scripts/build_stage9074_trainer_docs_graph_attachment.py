#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9074
NAME = "stage9074_trainer_docs_graph_attachment"
BASE_GRAPH = ROOT / "runs/local/artifacts/stage9067_trainer_dry_run_controls_graph_attachment/central_research_graph_with_trainer_dry_run_controls.json"
SOURCE_9072 = ROOT / "runs/summaries/stage9072_trainer_dry_run_documentation_refresh.json"
SOURCE_9073 = ROOT / "runs/summaries/stage9073_central_graph_gap_walk_after_trainer_docs.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DOCS_GRAPH_ATTACHMENT_STAGE9074.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_trainer_docs_contract.json"
CARD = OUT_DIR / "trainer_docs_graph_attachment_card.json"

NEW_NODES = [
    {"id": "contract:trainer_dry_run_recovered_contract_v1", "kind": "contract", "node_type": "contract", "status": "documented_no_execution_contract", "summary": "runs/summaries/stage9072_trainer_dry_run_documentation_refresh.json", "authority": AUTHORITY_CLOSED},
    {"id": "doc:trainer_dry_run_recovered_contract_stage9072", "kind": "doc", "node_type": "doc", "status": "recovered_contract_doc", "path": "docs/TRAINER_DRY_RUN_RECOVERED_CONTRACT_STAGE9072.md", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_required_inputs_complete", "kind": "gate", "node_type": "gate", "status": "required_before_dry_run_execution", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_long_context_inputs_required", "kind": "gate", "node_type": "gate", "status": "required_before_dry_run_execution", "authority": AUTHORITY_CLOSED},
    {"id": "gate:trainer_no_execution_documented", "kind": "gate", "node_type": "gate", "status": "blocks_execution_from_docs_stage", "authority": AUTHORITY_CLOSED},
    {"id": "telemetry:trainer_dry_run_required_stubs", "kind": "telemetry", "node_type": "telemetry", "status": "required_before_dry_run_execution", "authority": AUTHORITY_CLOSED},
    {"id": "forbidden_ops:trainer_dry_run_forbidden_operations", "kind": "forbidden_ops", "node_type": "forbidden_ops", "status": "required_before_dry_run_execution", "authority": AUTHORITY_CLOSED},
]

NEW_EDGES = [
    ("contract:trainer_dry_run_recovered_contract_v1", "documents", "contract:trainer_dry_run_input_long_context_v1"),
    ("contract:trainer_dry_run_recovered_contract_v1", "documented_by", "doc:trainer_dry_run_recovered_contract_stage9072"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_required_inputs_complete"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_long_context_inputs_required"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_no_execution_documented"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "telemetry:trainer_dry_run_required_stubs"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "forbidden_ops:trainer_dry_run_forbidden_operations"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:model_forward"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:dataset_row_load"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:trainer_execution"),
    ("gate:trainer_long_context_inputs_required", "requires", "gate:long_context_compiler_handoff_blocker_v1"),
    ("gate:trainer_long_context_inputs_required", "requires", "preflight:long_context_loss_mask_compiler_v1"),
    ("gate:trainer_long_context_inputs_required", "requires", "gate:long_context_route_card_materialization_audit_v1"),
]

PLACEHOLDER_TARGET_PREFIXES = {
    "contract:": "contract",
    "doc:": "doc",
    "gate:": "gate",
    "preflight:": "preflight",
    "telemetry:": "telemetry",
    "forbidden_ops:": "forbidden_ops",
    "operation:": "operation",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = str(node["id"])
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = dict(node)
    return True


def ensure_placeholder(nodes: dict[str, dict[str, Any]], node_id: str) -> None:
    if node_id in nodes:
        return
    for prefix, kind in PLACEHOLDER_TARGET_PREFIXES.items():
        if node_id.startswith(prefix):
            add_node(nodes, {"id": node_id, "kind": kind, "node_type": kind, "status": "recovered_placeholder", "authority": AUTHORITY_CLOSED})
            return


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": NAME})
    return True


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source_9072 = load_json(SOURCE_9072)
    source_9073 = load_json(SOURCE_9073)
    graph = load_json(BASE_GRAPH)
    nodes = {str(node.get("id")): dict(node) for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = sum(1 for node in NEW_NODES if add_node(nodes, node))
    added_edges = 0
    for source, relation, target in NEW_EDGES:
        ensure_placeholder(nodes, source)
        ensure_placeholder(nodes, target)
        added_edges += int(add_edge(edges, source, relation, target))
    out_graph = {
        **graph,
        "version": NAME,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": sorted(nodes.values(), key=lambda row: str(row.get("id"))),
        "edges": sorted(edges, key=lambda row: (str(row.get("source")), str(row.get("relation")), str(row.get("target")))),
        "authority": dict(AUTHORITY_CLOSED),
    }
    present_nodes = {node.get("id") for node in out_graph["nodes"]}
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out_graph["edges"]}
    authority_rows = sum(1 for node in out_graph["nodes"] if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    checks = {
        "source_stage9072_present": SOURCE_9072.exists(),
        "source_stage9072_passed": source_9072.get("passed") is True,
        "source_stage9073_present": SOURCE_9073.exists(),
        "source_stage9073_passed": source_9073.get("passed") is True,
        "base_graph_present": BASE_GRAPH.exists(),
        "new_nodes_present": {node["id"] for node in NEW_NODES}.issubset(present_nodes),
        "new_edges_present": set(NEW_EDGES).issubset(present_edges),
        "stage9073_identified_gap": (source_9073.get("metrics") or {}).get("stage9072_missing_nodes", 0) > 0,
        "authority_rows_zero": authority_rows == 0,
        "stage9072_trainer_not_invoked": (source_9072.get("metrics") or {}).get("trainer_invoked") is False,
        "registry_frontier_stage9073": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9073,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINER_DOCS_GRAPH_ATTACHMENT_NO_EXECUTION",
        "graph": out_graph,
        "new_node_ids": [node["id"] for node in NEW_NODES],
        "new_edges": [list(edge) for edge in NEW_EDGES],
        "checks": checks,
        "metrics": {
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(out_graph["nodes"]),
            "graph_edges": len(out_graph["edges"]),
            "authority_rows": authority_rows,
            "trainer_invoked": False,
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "candidate_rows_materialized": 0,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Attached Stage9072 recovered trainer dry-run documentation contract to the central graph as metadata-only controls. Trainer execution, row loading, mining, model forward, decoder CE, denoise CE, runtime, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9073, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if card["metrics"].get("added_nodes", 0) < len(NEW_NODES):
        failures.append("missing_added_nodes")
    if card["metrics"].get("added_edges", 0) < len(NEW_EDGES):
        failures.append("missing_added_edges")
    for key in [
        "trainer_invoked",
        "trainer_dry_run_executed_now",
        "model_forward_attempted",
        "dataset_rows_loaded",
        "repository_source_bodies_loaded",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    if card["metrics"].get("candidate_rows_materialized") != 0:
        failures.append("candidate_rows_materialized")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    built = build_card(registry)
    graph = built.pop("graph")
    failures = validate_card(built, registry)
    GRAPH.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    CARD.write_text(json.dumps(built, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **built["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "graph": str(GRAPH.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": built["decision"] if not failures else "Trainer docs graph attachment failed.",
        "next_best_step": "Continue no-data recovery with current frontier reconciliation after Stage9074, or design a future source/output ticket without reading row bodies.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9074 Trainer Docs Graph Attachment",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Attached the Stage9072 recovered trainer dry-run documentation contract to the central graph as metadata-only controls.",
        "",
        f"Added nodes: `{built['metrics']['added_nodes']}`",
        f"Added edges: `{built['metrics']['added_edges']}`",
        "",
        "Still closed: trainer execution, row loading, source/body loading, candidate mining, model forward, decoder CE, denoise CE, runtime, /arxiv compiler IO, and training.",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage9074 Trainer Docs Graph Attachment"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9074 attaches the Stage9072 recovered trainer dry-run documentation contract to the central graph as metadata-only nodes and edges.",
            "",
            "Trainer execution, row loading, repository source/body loading, candidate mining, model forward, decoder CE, denoise CE, runtime, /arxiv compiler IO, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
