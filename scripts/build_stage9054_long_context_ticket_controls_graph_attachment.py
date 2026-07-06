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
STAGE = 9054
NAME = "stage9054_long_context_ticket_controls_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8898_policy_evolution_knowledge_transfer_graph_attachment/central_research_graph_with_policy_evolution_knowledge_transfer.json"
SOURCE_9053 = ROOT / "runs/summaries/stage9053_long_context_source_output_ticket_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_TICKET_CONTROLS_GRAPH_ATTACHMENT_STAGE9054.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
GRAPH = OUT_DIR / "central_research_graph_with_long_context_ticket_controls.json"
NODES = OUT_DIR / "central_research_graph_with_long_context_ticket_controls_nodes.jsonl"
EDGES = OUT_DIR / "central_research_graph_with_long_context_ticket_controls_edges.jsonl"
CARD = OUT_DIR / "long_context_ticket_controls_graph_attachment_card.json"

NEW_NODES = [
    {
        "id": "gate:long_context_source_output_ticket_v1",
        "kind": "gate",
        "node_type": "gate",
        "status": "inactive_template_audited_no_data_read",
        "summary": "runs/summaries/stage9053_long_context_source_output_ticket_audit.json",
        "authority": AUTHORITY_CLOSED,
    },
    {
        "id": "support_module:long_context_candidate_miner_guarded",
        "kind": "support_module",
        "node_type": "support_module",
        "status": "guarded_fixture_only_until_ticket",
        "summary": "runs/summaries/stage9051_long_context_candidate_miner_guard_audit.json",
        "authority": AUTHORITY_CLOSED,
    },
    {
        "id": "support_module:long_context_corpus_index_guarded",
        "kind": "support_module",
        "node_type": "support_module",
        "status": "guarded_fixture_only_until_ticket",
        "summary": "runs/summaries/stage9050_long_context_term_noise_filter_audit.json",
        "authority": AUTHORITY_CLOSED,
    },
    {
        "id": "control_contract:no_real_long_context_mining_without_ticket",
        "kind": "control_contract",
        "node_type": "control_contract",
        "status": "active_closed_contract",
        "authority": AUTHORITY_CLOSED,
    },
]
NEW_EDGES = [
    ("gate:long_context_source_output_ticket_v1", "guards", "support_module:long_context_corpus_index_guarded"),
    ("gate:long_context_source_output_ticket_v1", "guards", "support_module:long_context_candidate_miner_guarded"),
    ("control_contract:no_real_long_context_mining_without_ticket", "blocks_without_ticket", "operation:scan_arxiv"),
    ("control_contract:no_real_long_context_mining_without_ticket", "blocks_without_ticket", "operation:run_candidate_mining"),
    ("control_contract:no_real_long_context_mining_without_ticket", "blocks_without_ticket", "operation:write_candidates_under_arxiv"),
    ("support_module:long_context_corpus_index_guarded", "feeds_after_ticket", "support_module:long_context_candidate_miner_guarded"),
    ("support_module:long_context_candidate_miner_guarded", "future_feeds", "compiler_stage:curriculum_compiler"),
    ("support_module:long_context_candidate_miner_guarded", "requires_before_compiler", "support_module:dataset_junk_ood_ranker_v1"),
    ("support_module:long_context_candidate_miner_guarded", "requires_before_compiler", "gate:shortcut_baseline_audit"),
    ("gate:long_context_source_output_ticket_v1", "preserves", "boundary:do_not_train_what_tools_can_observe"),
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = str(node["id"])
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = dict(node)
    return True


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    edge = {"source": source, "relation": relation, "target": target, "evidence_source": NAME}
    if edge in edges:
        return False
    if any(existing.get("source") == source and existing.get("relation") == relation and existing.get("target") == target for existing in edges):
        return False
    edges.append(edge)
    return True


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def build_graph_card() -> dict[str, Any]:
    source = load_json(SOURCE_9053)
    graph = load_json(BASE)
    nodes = {str(node.get("id")): dict(node) for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    added_edges = 0
    for node in NEW_NODES:
        added_nodes += int(add_node(nodes, node))
    for source_id, relation, target in NEW_EDGES:
        if target.startswith("operation:") and target not in nodes:
            add_node(nodes, {"id": target, "kind": "operation", "node_type": "operation", "status": "blocked_without_ticket", "authority": AUTHORITY_CLOSED})
        added_edges += int(add_edge(edges, source_id, relation, target))
    out = {
        **graph,
        "version": NAME,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "nodes": sorted(nodes.values(), key=lambda item: str(item.get("id"))),
        "edges": sorted(edges, key=lambda item: (str(item.get("source")), str(item.get("relation")), str(item.get("target")))),
        "authority": AUTHORITY_CLOSED,
    }
    expected = {node["id"] for node in NEW_NODES}
    present = {node.get("id") for node in out["nodes"]}
    required_edges = {(src, rel, dst) for src, rel, dst in NEW_EDGES}
    present_edges = {(edge.get("source"), edge.get("relation"), edge.get("target")) for edge in out["edges"]}
    missing_nodes = sorted(expected - present)
    missing_edges = sorted(required_edges - present_edges)
    failures = []
    if source.get("passed") is not True:
        failures.append("source_stage9053_not_passed")
    if missing_nodes:
        failures.append("missing_nodes")
    if missing_edges:
        failures.append("missing_edges")
    authority_rows = sum(1 for node in out["nodes"] if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    if authority_rows:
        failures.append("authority_open_in_nodes")
    return {
        "passed": not failures,
        "failures": failures,
        "graph": out,
        "added_nodes": added_nodes,
        "added_edges": added_edges,
        "missing_nodes": missing_nodes,
        "missing_edges": missing_edges,
        "authority_rows": authority_rows,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    built = build_graph_card()
    graph = built.pop("graph")
    GRAPH.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_jsonl(NODES, graph["nodes"])
    write_jsonl(EDGES, graph["edges"])
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": built["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": built["authority_rows"],
            "failures": built["failures"],
            "added_nodes": built["added_nodes"],
            "added_edges": built["added_edges"],
            "graph_nodes": len(graph["nodes"]),
            "graph_edges": len(graph["edges"]),
            "source_reads_authorized_now": False,
            "candidate_mining_authorized_now": False,
            "training_authorized": False,
        },
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "nodes_jsonl": str(NODES.relative_to(ROOT)), "edges_jsonl": str(EDGES.relative_to(ROOT)), "card": str(CARD.relative_to(ROOT))},
        "decision": "Attached long-context source/output ticket controls to the central graph; real mining remains ticket-blocked.",
        "next_best_step": "Audit candidate quality/routing on synthetic fixtures only, or continue no-data compiler recovery; do not scan real corpora.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9054 Long Context Ticket Controls Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached long-context guarded corpus-index/candidate-miner controls and the inactive source/output ticket gate to the central graph.",
        "",
        f"Added nodes: `{built['added_nodes']}`",
        f"Added edges: `{built['added_edges']}`",
        "",
        "No real source reads, candidate mining, `/arxiv` writes, model execution, or training are authorized.",
        "",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
