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
STAGE = 9071
NAME = "stage9071_current_frontier_reconciliation_after_long_context_guards"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_RECONCILIATION_AFTER_LONG_CONTEXT_GUARDS_STAGE9071.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_reconciliation_after_long_context_guards.json"

SOURCE_SUMMARIES = {
    9064: "stage9064_training_readiness_refresh_after_long_context_controls",
    9065: "stage9065_trainer_dry_run_input_refresh_after_long_context_controls",
    9066: "stage9066_trainer_dry_run_input_negative_case_audit",
    9067: "stage9067_trainer_dry_run_controls_graph_attachment",
    9068: "stage9068_long_context_candidate_dispersion_guard_audit",
    9069: "stage9069_long_context_compound_term_index_guard_audit",
    9070: "stage9070_long_context_compound_candidate_ratio_guard_audit",
}

CURRENT_RECOVERED_CONTROLS = [
    "training_readiness_after_long_context_controls",
    "trainer_dry_run_requires_long_context_gate_inputs",
    "trainer_dry_run_negative_cases_rejected",
    "trainer_dry_run_controls_attached_to_graph",
    "candidate_dispersion_guard",
    "compound_identifier_index_terms",
    "compound_candidate_ratio_and_concept_row_guard",
]

CURRENT_BLOCKED_AUTHORITY = [
    "model_execution",
    "trainer_execution",
    "dataset_row_loading",
    "repository_source_body_loading",
    "candidate_mining",
    "index_building_from_real_sources",
    "arxiv_read_write_for_compiler",
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime_reward",
    "runtime_harness",
    "gemma",
    "harness_scoring",
    "controller_merge",
    "promotion",
]

NEXT_SAFE_BRANCHES = [
    "trainer documentation refresh for recovered dry-run inputs",
    "no-data central graph gap walk against Stage9071",
    "future source/output ticket design if user explicitly authorizes real row/index work",
    "future dry-run execution authorization only after all required inputs exist and a separate audit passes",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def summary_path(stage_name: str) -> Path:
    return ROOT / "runs/summaries" / f"{stage_name}.json"


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    sources: dict[str, dict[str, Any]] = {}
    for stage, stage_name in SOURCE_SUMMARIES.items():
        summary = load_json(summary_path(stage_name))
        sources[str(stage)] = {
            "stage_name": stage_name,
            "exists": bool(summary),
            "passed": summary.get("passed") is True,
            "next_best_step": summary.get("next_best_step"),
            "metrics": summary.get("metrics") or {},
        }
    s9064 = sources["9064"]["metrics"]
    s9065 = sources["9065"]["metrics"]
    s9066 = sources["9066"]["metrics"]
    s9067 = sources["9067"]["metrics"]
    s9068 = sources["9068"]["metrics"]
    s9069 = sources["9069"]["metrics"]
    s9070 = sources["9070"]["metrics"]
    checks = {
        "source_summaries_present": all(item["exists"] for item in sources.values()),
        "source_summaries_passed": all(item["passed"] for item in sources.values()),
        "recovered_controls_recorded": len(CURRENT_RECOVERED_CONTROLS) >= 7,
        "blocked_authority_recorded": len(CURRENT_BLOCKED_AUTHORITY) >= 15,
        "next_safe_branches_recorded": len(NEXT_SAFE_BRANCHES) >= 4,
        "stage9064_training_ready_false": s9064.get("training_ready") is False,
        "stage9065_dry_run_not_ready": s9065.get("dry_run_instance_ready_to_execute") is False,
        "stage9066_negative_cases_rejected": s9066.get("negative_cases_rejected") == s9066.get("negative_cases"),
        "stage9067_graph_attached_no_forward": s9067.get("model_forward_attempted") is False,
        "stage9068_no_candidates_materialized": s9068.get("candidate_rows_materialized") == 0,
        "stage9069_no_real_index_written": s9069.get("real_index_rows_written") == 0,
        "stage9070_no_candidate_mining": s9070.get("candidate_rows_materialized") == 0,
        "registry_frontier_stage9070": int((registry.get("metrics") or {}).get("latest_stage", -1)) == 9070,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_LONG_CONTEXT_GUARDS",
        "source_status": sources,
        "current_recovered_controls": CURRENT_RECOVERED_CONTROLS,
        "current_blocked_authority": CURRENT_BLOCKED_AUTHORITY,
        "next_safe_branches": NEXT_SAFE_BRANCHES,
        "checks": checks,
        "metrics": {
            "source_summaries": len(SOURCE_SUMMARIES),
            "source_summaries_passed": sum(1 for item in sources.values() if item["passed"]),
            "recovered_controls": len(CURRENT_RECOVERED_CONTROLS),
            "blocked_authority_count": len(CURRENT_BLOCKED_AUTHORITY),
            "next_safe_branches": len(NEXT_SAFE_BRANCHES),
            "training_ready": False,
            "dry_run_ready_to_execute": False,
            "trainer_dry_run_executed_now": False,
            "model_execution_attempted": False,
            "model_forward_attempted": False,
            "data_mining_authorized": False,
            "candidate_rows_materialized": 0,
            "real_index_rows_written": 0,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Current frontier is reconciled after Stage9070. Long-context/trainer controls are recovered, but real candidate mining, index building, trainer execution, model forward, decoder CE, denoise CE, runtime, and training remain closed.",
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9070, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "training_ready",
        "dry_run_ready_to_execute",
        "trainer_dry_run_executed_now",
        "model_execution_attempted",
        "model_forward_attempted",
        "data_mining_authorized",
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
    if card["metrics"].get("real_index_rows_written") != 0:
        failures.append("real_index_rows_written")
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
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Current frontier reconciliation after long-context guards failed.",
        "next_best_step": "Continue no-data recovery with trainer documentation refresh or graph gap walk. Real source/index/candidate work and trainer execution require separate explicit tickets.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9071 Current Frontier Reconciliation After Long-Context Guards",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Reconciles Stage9064-9070 into the current no-data recovery frontier. Long-context/trainer controls are recovered, but execution and mining remain closed.",
        "",
        f"Recovered controls: `{card['metrics']['recovered_controls']}`",
        f"Blocked authority entries: `{card['metrics']['blocked_authority_count']}`",
        f"Training ready: `{card['metrics']['training_ready']}`",
        f"Candidate rows materialized: `{card['metrics']['candidate_rows_materialized']}`",
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
    marker = "## Stage9071 Current Frontier Reconciliation After Long-Context Guards"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage9071 reconciles Stage9064-9070 into the current no-data recovery frontier. Training readiness, trainer dry-run input controls, negative-case audits, graph attachment, candidate dispersion, compound term indexing, and compound candidate ratio guards are recovered.",
            "",
            "Real source/index/candidate work, /arxiv compiler IO, trainer execution, model forward, decoder CE, denoise CE, runtime, Gemma, harness/scoring, controller merge, promotion, and training remain closed until separate explicit tickets and audits pass.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
