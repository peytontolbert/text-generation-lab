#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9688
NAME = "stage9688_locked_eval_guard_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8898_policy_evolution_knowledge_transfer_graph_attachment/central_research_graph_with_policy_evolution_knowledge_transfer.json"
SOURCE = ROOT / "runs/summaries/stage9687_locked_eval_train_exclusion_guard.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "V27_LOCKED_EVAL_GUARD_GRAPH_ATTACHMENT_STAGE9688.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


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


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
    registry["rows"] = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["passed"] = bool(registry["rows"])
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(registry["rows"]),
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load_json(BASE)
    source = load_json(SOURCE)
    metrics_src = source.get("metrics") or {}
    failures = [] if source.get("passed") is True else ["stage9687_not_passed"]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0

    guard = "control_card:locked_eval_train_exclusion_guard"
    compiler = "support_module:curriculum_compiler"
    locked_suite = "support_module:golden_locked_eval_suite"
    loss_masks = "control_card:loss_mask_authority"
    eval_contract = "objective:v27_multilingual_locked_eval_acceptance"
    train_manifests = "compiler_stage:training_manifest_materialization"

    added_nodes += int(add_node(nodes, {
        "id": guard,
        "kind": "control_card",
        "node_type": "control_card",
        "name": "locked_eval_train_exclusion_guard",
        "status": "passed_hard_compiler_guard",
        "summary": str(SOURCE.relative_to(ROOT)),
        "locked_source_exclusion_rows": metrics_src.get("locked_source_exclusion_rows"),
        "decoder_ce_loss_rows_after_guard": metrics_src.get("decoder_ce_loss_rows"),
        "blocked_with_forbidden_loss": metrics_src.get("blocked_with_forbidden_loss"),
        "purpose": "Prevent locked regression, hidden, promotion-only, or otherwise excluded eval sources from entering any train-eligible curriculum manifest.",
        "authority": dict(AUTHORITY_CLOSED),
    }))
    for node_id, kind in [
        (compiler, "support_module"),
        (locked_suite, "support_module"),
        (loss_masks, "control_card"),
        (eval_contract, "objective"),
        (train_manifests, "compiler_stage"),
        ("objective:bounded_decoder_ce", "objective"),
        ("objective:denoise_repair", "objective"),
        ("objective:structured_state", "objective"),
    ]:
        add_node(nodes, {"id": node_id, "kind": kind, "node_type": kind, "authority": dict(AUTHORITY_CLOSED)})

    add_edge(edges, locked_suite, "provides_locked_source_ids_to", guard)
    add_edge(edges, guard, "hard_blocks_train_rows_for", train_manifests)
    add_edge(edges, guard, "runs_before_loss_mask_creation_in", compiler)
    add_edge(edges, guard, "prevents_eval_contamination_of", "objective:bounded_decoder_ce")
    add_edge(edges, guard, "prevents_eval_contamination_of", "objective:denoise_repair")
    add_edge(edges, guard, "prevents_eval_contamination_of", "objective:structured_state")
    add_edge(edges, eval_contract, "requires_exclusion_guard", guard)
    add_edge(edges, guard, "guards", loss_masks)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_locked_eval_guard.json"
    nodes_path = OUT_DIR / "central_research_graph_with_locked_eval_guard_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_locked_eval_guard_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    if metrics_src.get("locked_source_exclusion_rows") != 3:
        failures.append("stage9687_locked_exclusion_count_unexpected")
    if metrics_src.get("decoder_ce_loss_rows") != 1:
        failures.append("stage9687_decoder_guard_unexpected")
    if metrics_src.get("blocked_with_forbidden_loss"):
        failures.append("blocked_rows_with_forbidden_loss")

    next_step = "Resume non-eval training package selection with --locked-source-exclusions required, then run contract-only target_100m preflight under the locked-source guard."
    metrics = {
        **dict(AUTHORITY_CLOSED),
        "authority_rows": 0,
        "source_failures": failures,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "added_nodes": added_nodes,
        "locked_source_exclusion_rows": metrics_src.get("locked_source_exclusion_rows"),
        "decoder_ce_loss_rows_after_guard": metrics_src.get("decoder_ce_loss_rows"),
        "blocked_with_forbidden_loss_rows": len(metrics_src.get("blocked_with_forbidden_loss") or []),
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": metrics,
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "source_summary": str(SOURCE.relative_to(ROOT)),
        },
        "decision": "Attached the locked eval train-exclusion guard to the central research graph as a hard pre-loss-mask compiler control.",
        "next_best_step": next_step,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "locked_eval_guard_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9688 Locked Eval Guard Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        f"Graph nodes: `{metrics['graph_nodes']}`",
        f"Graph edges: `{metrics['graph_edges']}`",
        f"Locked exclusion rows in fixture: `{metrics['locked_source_exclusion_rows']}`",
        f"Decoder CE rows after guard: `{metrics['decoder_ce_loss_rows_after_guard']}`",
        "",
        "The central graph now records locked eval exclusion as a hard compiler control that runs before loss-mask creation.",
        "",
        "No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.",
        "",
        f"Next: {next_step}",
        "",
    ]), encoding="utf-8")
    if card["passed"]:
        update_registry(card)
    print(json.dumps({
        "stage": STAGE,
        "passed": card["passed"],
        "failures": failures,
        "graph_nodes": metrics["graph_nodes"],
        "graph_edges": metrics["graph_edges"],
        "next_best_step": next_step,
    }, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
