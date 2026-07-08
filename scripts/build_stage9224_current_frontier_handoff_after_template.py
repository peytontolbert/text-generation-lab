#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9224
NAME = "stage9224_current_frontier_handoff_after_template"
PREV_SUMMARY = ROOT / "runs/summaries/stage9223_inactive_final_preexecution_audit_template.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9223_inactive_final_preexecution_audit_template/inactive_final_preexecution_audit_template.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_handoff_after_template.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_HANDOFF_AFTER_TEMPLATE_STAGE9224.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

FRONTIER_FACTS = [
    "stage9218_all_three_repo_local_families_have_inactive_audited_ticket_coverage",
    "stage9219_frontier_reconciled_after_ticket_coverage",
    "stage9220_ticket_coverage_not_trainer_execution_readiness",
    "stage9221_no_execution_next_decision_map_active",
    "stage9222_family_specific_preexecution_gaps_recorded",
    "stage9223_inactive_final_preexecution_audit_template_available",
]

ONLY_VALID_NEXT_BRANCHES = [
    "stop_and_wait_for_explicit_one_family_request",
    "continue_no_execution_documentation_or_central_graph_review",
    "if_user_selects_exactly_one_family_build_family_specific_final_preexecution_audit_design_only",
]

INVALID_NEXT_BRANCHES = [
    "run_trainer",
    "run_model_forward_or_generation",
    "run_backward_or_optimizer",
    "write_or_export_checkpoint",
    "execute_cleanup",
    "read_write_or_mine_arxiv",
    "run_runtime_or_verifier_runtime",
    "emit_source_body_or_patch_body",
    "run_gemma_harness_or_scoring",
    "merge_controller_or_promote",
]

RESUME_POINTERS = {
    "registry": "runs/local/artifacts/reconstructed_stage_registry.json",
    "inactive_template": "runs/local/artifacts/stage9223_inactive_final_preexecution_audit_template/inactive_final_preexecution_audit_template.json",
    "gap_map": "runs/local/artifacts/stage9222_family_specific_preexecution_gap_map/family_specific_preexecution_gap_map.json",
    "decision_map": "runs/local/artifacts/stage9221_no_execution_next_decision_map/no_execution_next_decision_map.json",
    "readiness_ledger": "runs/local/artifacts/stage9220_no_execution_trainer_readiness_gap_ledger/no_execution_trainer_readiness_gap_ledger.json",
}

CLOSED_METRICS = [
    "trainer_executed_now",
    "model_forward_attempted",
    "generation_attempted",
    "backward_attempted",
    "optimizer_created",
    "checkpoint_written_now",
    "checkpoint_export_authorized",
    "cleanup_authorized_now",
    "cleanup_executed_now",
    "runtime_authorized_flag",
    "runtime_verifier_execution_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "arxiv_read_authorized_for_compiler",
    "arxiv_write_authorized",
    "data_mining_authorized",
    "live_ticket_materialized_now",
    "final_pre_execution_audit_authorized_now",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    checks = {
        "previous_stage9223_passed": prev.get("passed") is True,
        "registry_frontier_stage9223_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9223,
        "inactive_template_exists_and_supports_three_families": len(prev_card.get("supported_families") or []) == 3,
        "resume_pointers_all_exist": all((ROOT / path).exists() for path in RESUME_POINTERS.values()),
        "only_valid_next_branches_recorded": len(ONLY_VALID_NEXT_BRANCHES) == 3,
        "invalid_next_branches_block_execution_cleanup_arxiv": {"run_trainer", "execute_cleanup", "read_write_or_mine_arxiv"}.issubset(set(INVALID_NEXT_BRANCHES)),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "frontier_facts": len(FRONTIER_FACTS),
        "only_valid_next_branches": len(ONLY_VALID_NEXT_BRANCHES),
        "invalid_next_branches": len(INVALID_NEXT_BRANCHES),
        "resume_pointers": len(RESUME_POINTERS),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_HANDOFF_AFTER_INACTIVE_TEMPLATE_NO_EXECUTION",
        "frontier_facts": list(FRONTIER_FACTS),
        "only_valid_next_branches": list(ONLY_VALID_NEXT_BRANCHES),
        "invalid_next_branches": list(INVALID_NEXT_BRANCHES),
        "resume_pointers": dict(RESUME_POINTERS),
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Current frontier handoff recorded after the inactive final pre-execution audit template. The project is "
            "ready to pause or continue no-execution graph review; any future training path still requires explicit "
            "selection of exactly one family and a family-specific final pre-execution audit design."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for required in [
        "stop_and_wait_for_explicit_one_family_request",
        "continue_no_execution_documentation_or_central_graph_review",
        "if_user_selects_exactly_one_family_build_family_specific_final_preexecution_audit_design_only",
    ]:
        if required not in card.get("only_valid_next_branches", []):
            failures.append(f"missing_valid_branch:{required}")
    for invalid in ["run_trainer", "execute_cleanup", "read_write_or_mine_arxiv"]:
        if invalid not in card.get("invalid_next_branches", []):
            failures.append(f"missing_invalid_branch:{invalid}")
    for metric in CLOSED_METRICS:
        if card.get("metrics", {}).get(metric) is not False:
            failures.append(metric)
    return failures


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
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_spine(summary: dict[str, Any]) -> None:
    marker = "## Stage9224 Current Frontier Handoff After Template"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9224 is a compact handoff after Stage9223. The active repo-local trainer path has inactive ticket coverage, a readiness gap ledger, a decision map, a family-specific gap map, and an inactive final pre-execution audit template.",
        "The only valid branches are pause, continue no-execution central graph review, or build a family-specific final pre-execution audit design after the user explicitly selects exactly one family.",
        "All trainer/model/runtime/cleanup/mining/arxiv/source-body/Gemma/scoring/promotion authority remains closed.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    SPINE.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = build_card()
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Current frontier handoff after template failed.",
        "next_best_step": "Pause or continue no-execution central graph review; do not instantiate a live family audit without explicit one-family request.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9224 Current Frontier Handoff After Template",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Frontier facts:",
        *[f"- `{fact}`" for fact in FRONTIER_FACTS],
        "",
        "Only valid next branches:",
        *[f"- `{branch}`" for branch in ONLY_VALID_NEXT_BRANCHES],
        "",
        "Invalid next branches:",
        *[f"- `{branch}`" for branch in INVALID_NEXT_BRANCHES],
        "",
        "Resume pointers:",
        *[f"- `{key}`: `{value}`" for key, value in RESUME_POINTERS.items()],
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
