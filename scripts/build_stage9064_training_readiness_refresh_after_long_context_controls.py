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
STAGE = 9064
NAME = "stage9064_training_readiness_refresh_after_long_context_controls"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_READINESS_REFRESH_AFTER_LONG_CONTEXT_CONTROLS_STAGE9064.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "training_readiness_refresh_after_long_context_controls.json"

SOURCE_SUMMARIES = {
    9059: "stage9059_long_context_route_card_materialization_audit_contract",
    9060: "stage9060_long_context_candidate_quality_guard_refresh_audit",
    9061: "stage9061_long_context_compiler_handoff_blocker_audit",
    9062: "stage9062_long_context_loss_mask_compiler_preflight",
    9063: "stage9063_long_context_compiler_loss_mask_graph_attachment",
}

READY_NO_EXECUTION_COMPONENTS = [
    "long_context_route_card_materialization_audit_contract",
    "long_context_candidate_quality_guard_refresh",
    "long_context_compiler_handoff_blocker",
    "long_context_route_to_trainer_loss_mask_preflight",
    "central_graph_attachment_for_long_context_controls",
    "candidate_miner_guarded_by_source_ticket",
    "route_card_schema_defaults_all_losses_closed",
    "compiler_handoff_requires_judge_shortcut_counterfactual_split_loss_telemetry",
]

TRAINING_BLOCKERS = [
    {"id": "source_output_ticket_not_granted", "severity": "hard_block", "required_before_training": "granted scoped source/output ticket with /arxiv read/write decision"},
    {"id": "route_cards_not_materialized", "severity": "hard_block", "required_before_training": "route-card materialization audit must pass after granted ticket"},
    {"id": "compiler_handoff_blocked", "severity": "hard_block", "required_before_training": "Stage9061 artifacts must all pass for each route card before compiler handoff"},
    {"id": "loss_mask_translation_preflight_only", "severity": "hard_block", "required_before_training": "route losses must be translated into trainer loss masks and separately authorized"},
    {"id": "decoder_denoise_runtime_losses_closed", "severity": "hard_block", "required_before_training": "decoder CE, denoise CE, and runtime reward require separate future tickets"},
    {"id": "no_real_long_context_rows_compiled", "severity": "hard_block", "required_before_training": "no long-context candidates or route cards are compiler-ready now"},
    {"id": "graph_attachment_is_not_authority", "severity": "interpretation_block", "required_before_training": "central graph nodes only record dependencies; they do not authorize execution"},
    {"id": "training_authority_closed", "severity": "hard_block", "required_before_training": "explicit one-run training authorization review card plus pre-execution audit"},
]

NEXT_SAFE_BRANCHES = [
    "continue no-data trainer/compiler recovery",
    "refresh trainer dry-run contract to consume loss-mask preflight artifacts without model forward",
    "centralize route-card/materialization gate documentation in the research graph",
    "only after explicit ticket, materialize a tiny route-card sample and audit it without training",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_matrix(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "metrics": summary.get("metrics") or {},
        }
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "ready_no_execution_components_recorded": len(READY_NO_EXECUTION_COMPONENTS) >= 8,
        "training_blockers_recorded": len(TRAINING_BLOCKERS) >= 8,
        "all_blockers_are_blocks_or_interpretation_blocks": all(row["severity"] in {"hard_block", "interpretation_block"} for row in TRAINING_BLOCKERS),
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "route_rows_not_materialized": sources["9059"]["metrics"].get("route_rows_materialized_now") is False,
        "candidate_rows_not_materialized": sources["9060"]["metrics"].get("candidate_rows_materialized") == 0,
        "compiler_ready_rows_zero": sources["9061"]["metrics"].get("compiler_ready_rows_now") == 0 and sources["9062"]["metrics"].get("compiler_ready_rows_now") == 0,
        "training_ready_rows_zero": sources["9061"]["metrics"].get("training_ready_rows_now") == 0 and sources["9062"]["metrics"].get("training_ready_rows_now") == 0,
        "decoder_denoise_runtime_closed": sources["9062"]["metrics"].get("decoder_ce_authorized") is False and sources["9062"]["metrics"].get("denoise_ce_authorized") is False and sources["9062"]["metrics"].get("runtime_authorized_flag") is False,
        "graph_attachment_keeps_training_closed": sources["9063"]["metrics"].get("training_authorized") is False,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "registry_frontier_stage9063": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9063,
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "TRAINING_READINESS_BLOCKED_AFTER_LONG_CONTEXT_CONTROLS",
        "source_status": sources,
        "ready_no_execution_components": READY_NO_EXECUTION_COMPONENTS,
        "training_blockers": TRAINING_BLOCKERS,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "ready_no_execution_components": len(READY_NO_EXECUTION_COMPONENTS),
            "training_blockers": len(TRAINING_BLOCKERS),
            "hard_blockers": sum(1 for row in TRAINING_BLOCKERS if row["severity"] == "hard_block"),
            "interpretation_blockers": sum(1 for row in TRAINING_BLOCKERS if row["severity"] == "interpretation_block"),
            "training_ready": False,
            "actual_execution_authorized_next": False,
            "model_execution_attempted": False,
            "runtime_authorized_flag": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Long-context controls are recovered as no-data compiler/loss-mask blockers, but training remains hard-blocked until granted source tickets, materialized route cards, loss-mask authorization, and an explicit one-run execution audit exist.",
    }


def validate_matrix(matrix: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in matrix["checks"].items() if value is not True]
    if any((matrix.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9063, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in ["training_ready", "actual_execution_authorized_next", "model_execution_attempted", "runtime_authorized_flag", "training_authorized", "data_mining_authorized", "decoder_ce_authorized", "denoise_ce_authorized", "arxiv_read_authorized_for_compiler", "arxiv_write_authorized"]:
        if matrix["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    matrix = build_matrix(registry)
    failures = validate_matrix(matrix, registry)
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **matrix["metrics"]},
        "artifacts": {"matrix": str(MATRIX.relative_to(ROOT))},
        "decision": matrix["decision"] if not failures else "Training readiness refresh after long-context controls failed.",
        "next_best_step": "Continue no-data trainer/compiler recovery by refreshing trainer dry-run inputs to require Stage9061-9062 artifacts without model forward.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9064 Training Readiness Refresh After Long-Context Controls",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Long-context candidate, route-card, compiler handoff, and loss-mask controls are recovered as no-data blockers. They do not authorize training.",
        "",
        f"Training blockers: `{matrix['metrics']['training_blockers']}`",
        f"Training ready: `{matrix['metrics']['training_ready']}`",
        f"Data mining authorized: `{matrix['metrics']['data_mining_authorized']}`",
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
    marker = "## Stage9064 Training Readiness Refresh After Long-Context Controls"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9064 refreshes the training-readiness blocker matrix after long-context compiler handoff and route-to-trainer loss-mask controls. The controls are recovered, but source tickets, route-card materialization, compiler handoff, loss masks, model execution, mining, decoder CE, denoise CE, runtime, and training remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
