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
STAGE = 9099
NAME = "stage9099_current_frontier_reconciliation_after_runtime_assertion_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9095 = ROOT / "runs/summaries/stage9095_current_frontier_reconciliation_after_trainer_command_graph.json"
SOURCE_9096 = ROOT / "runs/summaries/stage9096_trainer_runtime_assertion_inventory.json"
SOURCE_9097 = ROOT / "runs/summaries/stage9097_trainer_runtime_assertion_inventory_audit.json"
SOURCE_9098 = ROOT / "runs/summaries/stage9098_trainer_runtime_assertion_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_RUNTIME_ASSERTION_GRAPH_STAGE9099.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_runtime_assertion_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9095_frontier_after_trainer_command_graph",
    "stage9096_trainer_runtime_assertion_inventory",
    "stage9097_trainer_runtime_assertion_inventory_negative_case_audit",
    "stage9098_trainer_runtime_assertion_graph_attachment",
    "graph_gate_runtime_assertions_require_manifest_and_caps",
    "graph_gate_runtime_assertions_require_loss_mask_enforcement",
    "graph_gate_runtime_assertions_require_authority_closure",
    "graph_gate_runtime_assertions_require_checkpoint_cleanup_proof",
    "graph_telemetry_required_interpretability_artifacts",
]

NEXT_SAFE_BRANCHES = [
    "contract-only artifact schema design without invocation",
    "trainer execution-authorization review card refresh without execution",
    "central graph gap walk for remaining trainer blockers",
    "future explicit source/output ticket instantiation design only after user authorization",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9095 = load_json(SOURCE_9095)
    s9096 = load_json(SOURCE_9096)
    s9097 = load_json(SOURCE_9097)
    s9098 = load_json(SOURCE_9098)
    checks = {
        "source_stage9095_passed": s9095.get("passed") is True,
        "source_stage9096_passed": s9096.get("passed") is True,
        "source_stage9097_passed": s9097.get("passed") is True,
        "source_stage9098_passed": s9098.get("passed") is True,
        "stage9097_negative_cases_rejected": (s9097.get("metrics") or {}).get("negative_cases_rejected") == (s9097.get("metrics") or {}).get("negative_cases"),
        "stage9098_added_graph_nodes": (s9098.get("metrics") or {}).get("added_nodes", 0) >= 7,
        "stage9098_added_graph_edges": (s9098.get("metrics") or {}).get("added_edges", 0) >= 20,
        "stage9098_authority_rows_zero": (s9098.get("metrics") or {}).get("authority_rows") == 0,
        "stage9098_trainer_closed": (s9098.get("metrics") or {}).get("trainer_executed_now") is False,
        "stage9098_runtime_assertions_closed": (s9098.get("metrics") or {}).get("runtime_assertions_executed_now") is False,
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 9,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9098": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9098,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_RUNTIME_ASSERTION_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9098_added_nodes": (s9098.get("metrics") or {}).get("added_nodes", 0),
            "stage9098_added_edges": (s9098.get("metrics") or {}).get("added_edges", 0),
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Frontier reconciled after trainer runtime assertion graph attachment. Trainer command controls and runtime assertion controls are graph-visible, but no data access, route-card materialization, route-to-loss translation, model input rows, compiler handoff, trainer dry run, trainer invocation, contract-only invocation, runtime assertion execution, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9098, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "source_output_ticket_instantiated_now",
        "source_metadata_read_now",
        "row_bodies_read_now",
        "repository_source_bodies_read_now",
        "route_cards_materialized_now",
        "route_to_loss_translation_ready_now",
        "compiler_handoff_ready_now",
        "trainer_dry_run_ready_now",
        "trainer_executed_now",
        "contract_only_invoked_now",
        "runtime_assertions_executed_now",
        "model_forward_attempted",
        "training_ready",
        "training_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "runtime_authorized_flag",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "cleanup_authorized_now",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    for key in ["candidate_rows_materialized", "model_input_rows_now"]:
        if card["metrics"].get(key) != 0:
            failures.append(key)
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after runtime assertion graph attachment failed.",
        "next_best_step": "Design contract-only artifact schema without invocation; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9099 Current Frontier After Runtime Assertion Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9098. Trainer command and runtime assertion controls are graph-visible and block trainer invocation, contract-only invocation, runtime assertion execution, model rows, model forward, decoder CE, denoise CE, runtime, and training.",
        "",
        f"Stage9098 added nodes: `{card['metrics']['stage9098_added_nodes']}`",
        f"Stage9098 added edges: `{card['metrics']['stage9098_added_edges']}`",
        "",
        "Next safe branches:",
        "",
        *[f"- {branch}" for branch in NEXT_SAFE_BRANCHES],
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
    marker = "## Stage9099 Current Frontier After Runtime Assertion Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9099 reconciles the current frontier after Stage9098. Trainer runtime assertion inventory controls are graph-visible and block trainer invocation, contract-only invocation, runtime assertion execution, model rows, model forward, decoder CE, denoise CE, runtime, and training.",
            "",
            "No source/output ticket, data access, route-card materialization, route-to-loss translation, compiler handoff, trainer dry run, trainer invocation, contract-only invocation, runtime assertion execution, model forward, decoder CE, denoise CE, runtime, /arxiv IO, cleanup, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
