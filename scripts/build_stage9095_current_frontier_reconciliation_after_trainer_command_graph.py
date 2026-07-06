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
STAGE = 9095
NAME = "stage9095_current_frontier_reconciliation_after_trainer_command_graph"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9091 = ROOT / "runs/summaries/stage9091_current_frontier_reconciliation_after_route_to_loss_graph.json"
SOURCE_9092 = ROOT / "runs/summaries/stage9092_trainer_command_surface_static_refresh.json"
SOURCE_9093 = ROOT / "runs/summaries/stage9093_trainer_command_surface_static_audit.json"
SOURCE_9094 = ROOT / "runs/summaries/stage9094_trainer_command_surface_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_TRAINER_COMMAND_GRAPH_STAGE9095.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_trainer_command_graph.json"

RECOVERED_RECENT_CONTROLS = [
    "stage9091_frontier_after_route_to_loss_graph",
    "stage9092_trainer_command_surface_static_refresh",
    "stage9093_trainer_command_surface_static_negative_case_audit",
    "stage9094_trainer_command_surface_graph_attachment",
    "graph_gate_trainer_command_requires_manifest_flag",
    "graph_gate_trainer_command_requires_mode_flag",
    "graph_gate_trainer_command_requires_loss_mask_audit_flag",
    "graph_gate_trainer_command_blocks_contract_invocation",
]

NEXT_SAFE_BRANCHES = [
    "trainer dry-run runtime assertion inventory no-execution refresh",
    "contract-only artifact schema design without invocation",
    "central graph gap walk for remaining trainer blockers",
    "future explicit source/output ticket instantiation design only after user authorization",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    s9091 = load_json(SOURCE_9091)
    s9092 = load_json(SOURCE_9092)
    s9093 = load_json(SOURCE_9093)
    s9094 = load_json(SOURCE_9094)
    checks = {
        "source_stage9091_passed": s9091.get("passed") is True,
        "source_stage9092_passed": s9092.get("passed") is True,
        "source_stage9093_passed": s9093.get("passed") is True,
        "source_stage9094_passed": s9094.get("passed") is True,
        "stage9093_negative_cases_rejected": (s9093.get("metrics") or {}).get("negative_cases_rejected") == (s9093.get("metrics") or {}).get("negative_cases"),
        "stage9094_added_graph_nodes": (s9094.get("metrics") or {}).get("added_nodes", 0) >= 6,
        "stage9094_added_graph_edges": (s9094.get("metrics") or {}).get("added_edges", 0) >= 16,
        "stage9094_authority_rows_zero": (s9094.get("metrics") or {}).get("authority_rows") == 0,
        "stage9094_trainer_closed": (s9094.get("metrics") or {}).get("trainer_executed_now") is False,
        "stage9094_contract_only_closed": (s9094.get("metrics") or {}).get("contract_only_invoked_now") is False,
        "recovered_recent_controls_recorded": len(RECOVERED_RECENT_CONTROLS) >= 8,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "registry_frontier_stage9094": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9094,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_TRAINER_COMMAND_GRAPH",
        "recovered_recent_controls": RECOVERED_RECENT_CONTROLS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "recovered_recent_controls": len(RECOVERED_RECENT_CONTROLS),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "stage9094_added_nodes": (s9094.get("metrics") or {}).get("added_nodes", 0),
            "stage9094_added_edges": (s9094.get("metrics") or {}).get("added_edges", 0),
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
        "decision": "Frontier reconciled after trainer command surface graph attachment. Source/output ticket, route-card audit, trainer input, route-to-loss, and trainer command controls are graph-visible, but no data access, route-card materialization, route-to-loss translation, model input rows, compiler handoff, trainer dry run, trainer invocation, contract-only invocation, model forward, decoder CE, denoise CE, runtime, or training is authorized.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9094, STAGE}:
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
        "decision": card["decision"] if not failures else "Current frontier reconciliation after trainer command graph attachment failed.",
        "next_best_step": "Refresh trainer dry-run runtime assertion inventory without invoking trainer; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9095 Current Frontier After Trainer Command Graph",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Recent controls are reconciled through Stage9094. Trainer command controls are graph-visible and block trainer invocation, contract-only invocation, model rows, model forward, decoder CE, denoise CE, runtime, and training.",
        "",
        f"Stage9094 added nodes: `{card['metrics']['stage9094_added_nodes']}`",
        f"Stage9094 added edges: `{card['metrics']['stage9094_added_edges']}`",
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
    marker = "## Stage9095 Current Frontier After Trainer Command Graph"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9095 reconciles the current frontier after Stage9094. Trainer command surface controls are graph-visible and block trainer invocation, contract-only invocation, model rows, model forward, decoder CE, denoise CE, runtime, and training.",
            "",
            "No source/output ticket, data access, route-card materialization, route-to-loss translation, compiler handoff, trainer dry run, trainer invocation, contract-only invocation, model forward, decoder CE, denoise CE, runtime, /arxiv IO, cleanup, or training is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
