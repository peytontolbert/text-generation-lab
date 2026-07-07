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
STAGE = 9219
NAME = "stage9219_current_frontier_reconciliation_after_ticket_coverage"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9218 = ROOT / "runs/summaries/stage9218_repo_local_ticket_coverage_final_matrix.json"
SOURCE_MATRIX = ROOT / "runs/local/artifacts/stage9218_repo_local_ticket_coverage_final_matrix/repo_local_ticket_coverage_final_matrix.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CURRENT_FRONTIER_AFTER_TICKET_COVERAGE_STAGE9219.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "current_frontier_after_ticket_coverage.json"

COVERED_FAMILIES = [
    "structured_policy_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

BLOCKED_UNTIL_EXPLICIT_REQUEST = [
    "final_pre_execution_audit",
    "live_one_run_ticket_materialization",
    "trainer_execution",
    "model_forward",
    "backward_or_optimizer_step",
    "checkpoint_write_or_export",
    "cleanup",
    "runtime_or_runtime_verifier",
    "arxiv_access_or_mining",
]

NEXT_ALLOWED_NO_EXECUTION_BRANCHES = [
    "refresh central graph docs only",
    "review unrelated long-context worktree files separately",
    "prepare a final pre-execution audit design only after explicit one-family request",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card(registry: dict[str, Any]) -> dict[str, Any]:
    source = load_json(SOURCE_9218)
    matrix = load_json(SOURCE_MATRIX)
    family_rows = matrix.get("family_ticket_coverage") or []
    covered = sorted(row.get("mode") for row in family_rows if row.get("passed") is True)
    registry_stage9218_passed = any(
        int(row.get("stage", -1)) == 9218 and row.get("passed") is True
        for row in registry.get("rows", [])
    )
    checks = {
        "source_stage9218_passed": source.get("passed") is True,
        "source_matrix_passed": matrix.get("passed") is True,
        "all_expected_families_covered": sorted(COVERED_FAMILIES) == covered,
        "family_ticket_audits_passed": (source.get("metrics") or {}).get("family_ticket_audits_passed") == 3,
        "blocked_items_recorded": len(BLOCKED_UNTIL_EXPLICIT_REQUEST) >= 9,
        "registry_contains_passed_stage9218": registry_stage9218_passed,
        "authority_counts_zero": not any(((registry.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "CURRENT_FRONTIER_RECONCILED_AFTER_REPO_LOCAL_TICKET_COVERAGE",
        "covered_families": covered,
        "blocked_until_explicit_request": list(BLOCKED_UNTIL_EXPLICIT_REQUEST),
        "next_allowed_no_execution_branches": list(NEXT_ALLOWED_NO_EXECUTION_BRANCHES),
        "checks": checks,
        "metrics": {
            "covered_families": len(covered),
            "blocked_until_explicit_request": len(BLOCKED_UNTIL_EXPLICIT_REQUEST),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "final_pre_execution_audit_authorized_now": False,
            "live_ticket_materialized_now": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "checkpoint_written_now": False,
            "cleanup_authorized_now": False,
            "runtime_authorized_flag": False,
            "runtime_verifier_execution_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Frontier reconciled after Stage9218: structured, bounded-decoder, and denoise repo-local families "
            "all have inactive audited ticket coverage. This is not execution authorization; final pre-execution "
            "audit and all trainer/model/runtime/cleanup paths remain blocked without an explicit one-family request."
        ),
    }


def validate_card(card: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card["checks"].items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9218, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    for key in [
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "final_pre_execution_audit_authorized_now",
        "live_ticket_materialized_now",
        "trainer_executed_now",
        "model_forward_attempted",
        "backward_attempted",
        "optimizer_created",
        "checkpoint_written_now",
        "cleanup_authorized_now",
        "runtime_authorized_flag",
        "runtime_verifier_execution_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
    return failures


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [
        row for row in registry.get("rows", [])
        if row.get("stage") != STAGE and row.get("stage_name") != NAME
    ]
    rows.append(
        {
            "stage": STAGE,
            "stage_name": NAME,
            "passed": summary["passed"],
            "path": str(SUMMARY),
            "authority": dict(AUTHORITY_CLOSED),
            "next_best_step": summary["next_best_step"],
        }
    )
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


def append_spine(summary: dict[str, Any], card: dict[str, Any]) -> None:
    marker = "## Stage9219 Current Frontier After Repo-Local Ticket Coverage"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in spine_text:
        return
    addition = "\n".join(
        [
            marker,
            "",
            "Stage9219 reconciles Stage9218 into the active frontier: structured-policy, bounded-decoder CE, and denoise-repair repo-local families have inactive audited ticket coverage.",
            "This opens no execution authority. A fresh final pre-execution audit remains blocked until an explicit request selects exactly one family.",
            "",
            "Still blocked: trainer execution, model forward/backward, optimizer, checkpoint writes/export, cleanup, runtime/runtime-verifier, decoder CE execution, denoise CE execution, /arxiv access, mining, source/body emission, Gemma, scoring, controller merge, and promotion.",
            "",
            f"Next: {summary['next_best_step']}",
            "",
        ]
    )
    SPINE.write_text(spine_text.rstrip() + "\n\n" + addition, encoding="utf-8")


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
        "artifacts": {
            "card": str(CARD.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": card["decision"] if not failures else "Current frontier reconciliation after ticket coverage failed.",
        "next_best_step": (
            "Stop before final pre-execution audit unless the user explicitly selects exactly one family for a future one-run request."
        ),
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9219 Current Frontier After Ticket Coverage",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "All three repo-local families have inactive audited ticket coverage.",
                "This stage does not authorize final pre-execution audit, trainer execution, model execution, runtime, cleanup, /arxiv access, or training.",
                "",
                f"Covered families: `{card['metrics']['covered_families']}`",
                f"Blocked items: `{card['metrics']['blocked_until_explicit_request']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    append_spine(summary, card)
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
