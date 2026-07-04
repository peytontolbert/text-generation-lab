#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "configs" / "software_maintainer" / "objective_rebuild_contracts.json"
SOURCES_PATH = ROOT / "runs" / "local" / "artifacts" / "stage8628_useful_recovery_integration" / "useful_recovery_sources.json"
GRAPH_PATH = ROOT / "runs" / "local" / "artifacts" / "stage8628_useful_recovery_integration" / "central_research_graph_with_useful_recoveries.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / "stage8629_recovery_completion_queue"
SUMMARY_PATH = ROOT / "runs" / "summaries" / "stage8629_recovery_completion_queue.json"
DOC_PATH = ROOT / "docs" / "RECOVERY_COMPLETION_QUEUE_STAGE8629.md"


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def source_matches(source: dict[str, Any], allowed_roles: list[str]) -> bool:
    return source.get("role") in set(allowed_roles)


def queue_item(objective: str, contract: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [s for s in sources if source_matches(s, contract.get("allowed_source_roles", []))]
    blockers: list[str] = []
    if contract["status"].startswith("missing"):
        blockers.append("builder_missing")
    if "partial" in contract["status"]:
        blockers.append("builder_partial_or_imbalanced")
    if not matched:
        blockers.append("no_stage8628_sources")
    blockers.extend(
        [
            "needs_source_inventory_card",
            "needs_route_card",
            "needs_loss_mask_card",
            "needs_counterfactual_obligation_card",
            "needs_shortcut_baseline_card",
            "needs_split_overlap_card",
        ]
    )
    return {
        "objective_family": objective,
        "priority": contract["priority"],
        "status": contract["status"],
        "default_route": contract["default_route"],
        "target_decisions": contract["target_decisions"],
        "required_counterfactuals": contract["required_counterfactuals"],
        "required_judge_gates": contract["required_judge_gates"],
        "allowed_source_roles": contract["allowed_source_roles"],
        "matched_source_count": len(matched),
        "matched_sources": [
            {
                "path": s["path"],
                "role": s["role"],
                "category": s["category"],
                "exists": s["exists"],
                "attach_to": s["attach_to"],
            }
            for s in matched[:20]
        ],
        "blockers": blockers,
        "done_definition": [
            "manifest builder exists with dry-run/no-op mode",
            "manifest emits row_id, objective_family, split, route, loss_mask, authority, model_input, clean_state",
            "dataset judge emits route cards for every row",
            "shortcut/baseline audit passes",
            "counterfactual sibling audit passes",
            "duplicate semantic key audit passes",
            "split overlap audit passes",
            "authority rows remain zero",
            "decoder_ce, denoise_ce, runtime_reward remain disabled unless explicitly authorized by later stage",
        ],
    }


def main() -> None:
    contract = read_json(CONTRACT_PATH)
    sources_doc = read_json(SOURCES_PATH)
    sources = sources_doc["sources"]
    graph = read_json(GRAPH_PATH)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = [
        queue_item(objective, item, sources)
        for objective, item in contract["objective_contracts"].items()
    ]
    items.sort(key=lambda x: x["priority"])

    queue = {
        "stage": 8629,
        "name": "stage8629_recovery_completion_queue",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "authority": AUTHORITY_CLOSED,
        "global_required_cards": contract["global_required_cards"],
        "global_forbidden_until_later_stage": contract["global_forbidden_until_later_stage"],
        "queue": items,
    }
    write_json(OUT_DIR / "recovery_completion_queue.json", queue)
    with (OUT_DIR / "recovery_completion_queue.jsonl").open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, sort_keys=True) + "\n")

    nodes = {n["id"]: n for n in graph["nodes"]}
    edges = list(graph["edges"])
    for item in items:
        obj_id = "objective_family:" + item["objective_family"]
        nodes.setdefault(
            obj_id,
            {
                "id": obj_id,
                "kind": "objective_family",
                "name": item["objective_family"],
                "recovered_from": "stage8629_recovery_completion_queue",
            },
        )
        queue_id = "recovery_queue:" + item["objective_family"]
        nodes[queue_id] = {
            "id": queue_id,
            "kind": "recovery_queue_item",
            "name": item["objective_family"],
            "priority": item["priority"],
            "status": item["status"],
            "matched_source_count": item["matched_source_count"],
            "recovered_from": "stage8629_recovery_completion_queue",
        }
        edges.append(
            {
                "source": queue_id,
                "target": obj_id,
                "relation": "rebuilds_objective",
                "evidence_source": "stage8629_recovery_completion_queue",
            }
        )
        for blocker in item["blockers"]:
            blocker_id = "recovery_blocker:" + blocker
            nodes.setdefault(
                blocker_id,
                {
                    "id": blocker_id,
                    "kind": "recovery_blocker",
                    "name": blocker,
                    "recovered_from": "stage8629_recovery_completion_queue",
                },
            )
            edges.append(
                {
                    "source": queue_id,
                    "target": blocker_id,
                    "relation": "blocked_by",
                    "evidence_source": "stage8629_recovery_completion_queue",
                }
            )

    graph2 = dict(graph)
    graph2["version"] = "stage8629_recovery_completion_queue"
    graph2["generated_at"] = queue["created_at_utc"]
    graph2["authority"] = AUTHORITY_CLOSED
    graph2["nodes"] = sorted(nodes.values(), key=lambda x: x["id"])
    graph2["edges"] = sorted(edges, key=lambda x: (x["source"], x["relation"], x["target"]))
    write_json(OUT_DIR / "central_research_graph_with_recovery_queue.json", graph2)
    with (OUT_DIR / "central_research_graph_with_recovery_queue_nodes.jsonl").open("w", encoding="utf-8") as f:
        for node in graph2["nodes"]:
            f.write(json.dumps(node, sort_keys=True) + "\n")
    with (OUT_DIR / "central_research_graph_with_recovery_queue_edges.jsonl").open("w", encoding="utf-8") as f:
        for edge in graph2["edges"]:
            f.write(json.dumps(edge, sort_keys=True) + "\n")

    missing_builders = [item["objective_family"] for item in items if item["status"].startswith("missing")]
    partial_builders = [item["objective_family"] for item in items if "partial" in item["status"]]
    source_ready = [item["objective_family"] for item in items if item["matched_source_count"] > 0]
    metrics = {
        "queue_items": len(items),
        "missing_builder_count": len(missing_builders),
        "partial_builder_count": len(partial_builders),
        "source_ready_count": len(source_ready),
        "graph_nodes": len(graph2["nodes"]),
        "graph_edges": len(graph2["edges"]),
        "objectives_with_sources": source_ready,
        "missing_builders": missing_builders,
        "partial_builders": partial_builders,
    }

    summary = {
        "stage": 8629,
        "stage_name": "stage8629_recovery_completion_queue",
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "queue": str((OUT_DIR / "recovery_completion_queue.json").relative_to(ROOT)),
            "queue_jsonl": str((OUT_DIR / "recovery_completion_queue.jsonl").relative_to(ROOT)),
            "graph": str((OUT_DIR / "central_research_graph_with_recovery_queue.json").relative_to(ROOT)),
            "contract": str(CONTRACT_PATH.relative_to(ROOT)),
            "row_judge": "scripts/objective_row_judge.py",
            "doc": str(DOC_PATH.relative_to(ROOT)),
        },
        "decision": "Missing recovery work is now centralized as objective-specific queue items with source mappings, judge gates, loss routes, and done definitions. No training/runtime/decode authority is opened.",
        "next_best_step": "Implement the first queue item: intent_to_build_strategy neutral masked builder plus route-card and shortcut audits.",
    }
    write_json(SUMMARY_PATH, summary)

    lines = [
        "# Stage8629 Recovery Completion Queue",
        "",
        "This stage centralizes everything still missing after Stage8628. It is a control-plane recovery artifact only. It does not authorize training, runtime, decoder CE, source/body emission, scoring, harness execution, controller merge, or promotion.",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(metrics, indent=2, sort_keys=True),
        "```",
        "",
        "## Recovery Queue",
        "",
    ]
    for item in items:
        lines.extend(
            [
                f"### {item['priority']}. `{item['objective_family']}`",
                "",
                f"- status: `{item['status']}`",
                f"- matched Stage8628 sources: `{item['matched_source_count']}`",
                f"- default route: `{item['default_route']}`",
                f"- blockers: `{', '.join(item['blockers'])}`",
                "",
                "Required gates:",
                "",
                *[f"- `{gate}`" for gate in item["required_judge_gates"]],
                "",
            ]
        )
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
