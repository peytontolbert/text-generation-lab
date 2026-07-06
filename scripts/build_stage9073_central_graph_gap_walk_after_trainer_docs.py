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
STAGE = 9073
NAME = "stage9073_central_graph_gap_walk_after_trainer_docs"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GRAPH = ROOT / "runs/local/artifacts/stage9067_trainer_dry_run_controls_graph_attachment/central_research_graph_with_trainer_dry_run_controls.json"
SOURCE_9072 = ROOT / "runs/summaries/stage9072_trainer_dry_run_documentation_refresh.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CENTRAL_GRAPH_GAP_WALK_AFTER_TRAINER_DOCS_STAGE9073.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "central_graph_gap_walk_after_trainer_docs.json"

REQUIRED_EXISTING_CONTROL_NODES = [
    "contract:trainer_dry_run_input_long_context_v1",
    "audit:trainer_dry_run_input_negative_cases_v1",
    "gate:trainer_stops_before_model_forward",
    "gate:no_trainer_row_or_weight_load",
    "gate:long_context_compiler_handoff_blocker_v1",
    "preflight:long_context_loss_mask_compiler_v1",
    "gate:long_context_route_card_materialization_audit_v1",
]

STAGE9072_EXPECTED_NODES = [
    "contract:trainer_dry_run_recovered_contract_v1",
    "doc:trainer_dry_run_recovered_contract_stage9072",
    "gate:trainer_required_inputs_complete",
    "gate:trainer_long_context_inputs_required",
    "gate:trainer_no_execution_documented",
    "telemetry:trainer_dry_run_required_stubs",
    "forbidden_ops:trainer_dry_run_forbidden_operations",
]

STAGE9072_EXPECTED_EDGES = [
    ("contract:trainer_dry_run_recovered_contract_v1", "documents", "contract:trainer_dry_run_input_long_context_v1"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_required_inputs_complete"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_long_context_inputs_required"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "gate:trainer_no_execution_documented"),
    ("contract:trainer_dry_run_recovered_contract_v1", "requires", "telemetry:trainer_dry_run_required_stubs"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:model_forward"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:dataset_row_load"),
    ("contract:trainer_dry_run_recovered_contract_v1", "blocks", "operation:trainer_execution"),
]

UNRESOLVED_GAPS = [
    {
        "priority": 1,
        "gap_id": "stage9072_graph_attachment_missing",
        "next_step": "Attach Stage9072 recovered trainer dry-run documentation contract to the central graph as metadata-only nodes and edges.",
        "authority_closed": True,
    },
    {
        "priority": 2,
        "gap_id": "source_output_ticket_missing_for_real_long_context_rows",
        "next_step": "Design a future source/output ticket before any real route-card materialization, index build, or candidate mining.",
        "authority_closed": True,
    },
    {
        "priority": 3,
        "gap_id": "trainer_contract_only_dry_run_inputs_unmaterialized",
        "next_step": "Keep trainer dry-run execution closed until locked manifest, loss-mask, schema lock, leakage proof, and long-context gate inputs exist.",
        "authority_closed": True,
    },
    {
        "priority": 4,
        "gap_id": "one_run_training_ticket_blocked",
        "next_step": "Do not instantiate a one-run training ticket until a real trainer contract-only dry run passes and emits required telemetry stubs.",
        "authority_closed": True,
    },
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    graph = load_json(GRAPH)
    source_9072 = load_json(SOURCE_9072)
    nodes = {str(node.get("id")) for node in graph.get("nodes", []) if node.get("id")}
    edges = {
        (str(edge.get("source")), str(edge.get("relation")), str(edge.get("target")))
        for edge in graph.get("edges", [])
        if edge.get("source") and edge.get("relation") and edge.get("target")
    }
    present_existing = sorted(node for node in REQUIRED_EXISTING_CONTROL_NODES if node in nodes)
    missing_existing = sorted(node for node in REQUIRED_EXISTING_CONTROL_NODES if node not in nodes)
    stage9072_present_nodes = sorted(node for node in STAGE9072_EXPECTED_NODES if node in nodes)
    stage9072_missing_nodes = sorted(node for node in STAGE9072_EXPECTED_NODES if node not in nodes)
    stage9072_present_edges = sorted(edge for edge in STAGE9072_EXPECTED_EDGES if edge in edges)
    stage9072_missing_edges = sorted(edge for edge in STAGE9072_EXPECTED_EDGES if edge not in edges)
    authority_rows = sum(1 for node in graph.get("nodes", []) if any((node.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED))
    checks = {
        "source_stage9072_present": SOURCE_9072.exists(),
        "source_stage9072_passed": source_9072.get("passed") is True,
        "base_graph_present": GRAPH.exists(),
        "existing_trainer_controls_attached": not missing_existing,
        "stage9072_attachment_gap_identified": bool(stage9072_missing_nodes or stage9072_missing_edges),
        "unresolved_gaps_recorded": len(UNRESOLVED_GAPS) >= 4,
        "authority_rows_zero": authority_rows == 0,
        "stage9072_training_closed": (source_9072.get("metrics") or {}).get("training_ready") is False,
        "stage9072_trainer_not_invoked": (source_9072.get("metrics") or {}).get("trainer_invoked") is False,
        "stage9072_no_candidate_rows": (source_9072.get("metrics") or {}).get("candidate_rows_materialized") == 0,
        "registry_frontier_stage9072": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9072,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CENTRAL_GRAPH_GAP_WALK_AFTER_TRAINER_DOCS_NO_EXECUTION",
        "graph_source": str(GRAPH.relative_to(ROOT)),
        "present_existing_control_nodes": present_existing,
        "missing_existing_control_nodes": missing_existing,
        "stage9072_present_nodes": stage9072_present_nodes,
        "stage9072_missing_nodes": stage9072_missing_nodes,
        "stage9072_present_edges": [list(edge) for edge in stage9072_present_edges],
        "stage9072_missing_edges": [list(edge) for edge in stage9072_missing_edges],
        "unresolved_gaps": UNRESOLVED_GAPS,
        "checks": checks,
        "metrics": {
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "existing_control_nodes": len(REQUIRED_EXISTING_CONTROL_NODES),
            "present_existing_control_nodes": len(present_existing),
            "missing_existing_control_nodes": len(missing_existing),
            "stage9072_expected_nodes": len(STAGE9072_EXPECTED_NODES),
            "stage9072_missing_nodes": len(stage9072_missing_nodes),
            "stage9072_expected_edges": len(STAGE9072_EXPECTED_EDGES),
            "stage9072_missing_edges": len(stage9072_missing_edges),
            "unresolved_gap_count": len(UNRESOLVED_GAPS),
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
        "decision": "Central graph gap walk confirms Stage9067 trainer controls are attached and Stage9072 recovered trainer documentation still needs a metadata-only graph attachment. Execution, mining, row loading, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9072, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if card["metrics"].get("missing_existing_control_nodes") != 0:
        failures.append("missing_existing_control_nodes")
    if card["metrics"].get("stage9072_missing_nodes", 0) == 0 and card["metrics"].get("stage9072_missing_edges", 0) == 0:
        failures.append("stage9072_gap_not_identified")
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
    card = build_card(registry)
    failures = validate_card(card, registry)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Central graph gap walk after Stage9072 failed.",
        "next_best_step": "Attach Stage9072 recovered trainer dry-run documentation contract to the central graph as metadata-only nodes and edges; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9073 Central Graph Gap Walk After Trainer Docs",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This no-data gap walk confirms the Stage9067 trainer dry-run controls are attached to the graph and identifies the remaining Stage9072 graph-attachment gap.",
        "",
        f"Existing control nodes present: `{card['metrics']['present_existing_control_nodes']}/{card['metrics']['existing_control_nodes']}`",
        f"Stage9072 missing graph nodes: `{card['metrics']['stage9072_missing_nodes']}`",
        f"Stage9072 missing graph edges: `{card['metrics']['stage9072_missing_edges']}`",
        "",
        "Priority gaps:",
        "",
        *[f"{gap['priority']}. `{gap['gap_id']}` - {gap['next_step']}" for gap in UNRESOLVED_GAPS],
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
    marker = "## Stage9073 Central Graph Gap Walk After Trainer Docs"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9073 confirms Stage9067 trainer dry-run controls are present in the central graph and records the next no-data gap: Stage9072 recovered trainer documentation needs a metadata-only graph attachment.",
            "",
            "Trainer execution, row loading, repository source/body loading, candidate mining, decoder CE, denoise CE, runtime, /arxiv compiler IO, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
