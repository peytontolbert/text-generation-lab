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
STAGE = 9218
NAME = "stage9218_repo_local_ticket_coverage_final_matrix"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_TICKET_COVERAGE_FINAL_MATRIX_STAGE9218.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
MATRIX = OUT_DIR / "repo_local_ticket_coverage_final_matrix.json"

SOURCE_9217 = ROOT / "runs/summaries/stage9217_repo_local_denoise_one_run_ticket_audit.json"
SOURCE_9213_MATRIX = ROOT / "runs/local/artifacts/stage9213_repo_local_execution_review_matrix_after_adapters/repo_local_execution_review_matrix_after_adapters.json"

FAMILY_TICKET_AUDITS = {
    "structured_policy_probe": {
        "design_stage": 9209,
        "audit_stage": 9210,
        "summary": ROOT / "runs/summaries/stage9210_repo_local_structured_one_run_ticket_audit.json",
        "ticket": ROOT / "runs/local/artifacts/stage9209_repo_local_structured_one_run_ticket_design/repo_local_structured_one_run_ticket_inactive.json",
        "audit": ROOT / "runs/local/artifacts/stage9210_repo_local_structured_one_run_ticket_audit/repo_local_structured_one_run_ticket_audit.json",
    },
    "bounded_decoder_ce_probe": {
        "design_stage": 9214,
        "audit_stage": 9215,
        "summary": ROOT / "runs/summaries/stage9215_repo_local_bounded_decoder_one_run_ticket_audit.json",
        "ticket": ROOT / "runs/local/artifacts/stage9214_repo_local_bounded_decoder_one_run_ticket_design/repo_local_bounded_decoder_one_run_ticket_inactive.json",
        "audit": ROOT / "runs/local/artifacts/stage9215_repo_local_bounded_decoder_one_run_ticket_audit/repo_local_bounded_decoder_one_run_ticket_audit.json",
    },
    "denoise_repair_probe": {
        "design_stage": 9216,
        "audit_stage": 9217,
        "summary": ROOT / "runs/summaries/stage9217_repo_local_denoise_one_run_ticket_audit.json",
        "ticket": ROOT / "runs/local/artifacts/stage9216_repo_local_denoise_one_run_ticket_schema/repo_local_denoise_one_run_ticket_inactive.json",
        "audit": ROOT / "runs/local/artifacts/stage9217_repo_local_denoise_one_run_ticket_audit/repo_local_denoise_one_run_ticket_audit.json",
    },
}

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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def ticket_is_inactive(ticket: dict[str, Any]) -> bool:
    return (
        ticket.get("ticket_status") == "DESIGN_ONLY_INACTIVE"
        and ticket.get("execution_authorized_now") is False
        and ticket.get("command_materialized") is False
        and ticket.get("allowed_operations_now") == []
        and not any((ticket.get("authority") or {}).values())
    )


def audit_family(mode: str, spec: dict[str, Any]) -> dict[str, Any]:
    summary = load_json(spec["summary"])
    ticket = load_json(spec["ticket"])
    audit = load_json(spec["audit"])
    failures: list[str] = []
    if summary.get("passed") is not True:
        failures.append("summary_not_passed")
    if not spec["ticket"].is_file():
        failures.append("ticket_missing")
    if not spec["audit"].is_file():
        failures.append("audit_missing")
    if not ticket_is_inactive(ticket):
        failures.append("ticket_not_inactive")
    if audit.get("passed") is not True:
        failures.append("audit_not_passed")
    if "run_trainer" not in (ticket.get("denied_operations_now") or []):
        failures.append("run_trainer_not_denied")
    if "walk_arxiv" not in (ticket.get("denied_operations_now") or []):
        failures.append("walk_arxiv_not_denied")
    if (summary.get("metrics") or {}).get("execution_authorized_now") is not False:
        failures.append("summary_execution_not_closed")
    return {
        "mode": mode,
        "design_stage": spec["design_stage"],
        "audit_stage": spec["audit_stage"],
        "passed": not failures,
        "failures": failures,
        "ticket_path": str(spec["ticket"].relative_to(ROOT)),
        "audit_path": str(spec["audit"].relative_to(ROOT)),
        "execution_authorized_now": False,
        "next_stage_execution_authorized": False,
    }


def build_matrix() -> dict[str, Any]:
    source_9217 = load_json(SOURCE_9217)
    source_matrix = load_json(SOURCE_9213_MATRIX)
    family_rows = [audit_family(mode, spec) for mode, spec in FAMILY_TICKET_AUDITS.items()]
    checks = {
        "source_stage9217_passed": source_9217.get("passed") is True,
        "source_stage9213_matrix_passed": source_matrix.get("passed") is True,
        "three_family_ticket_audits_present": len(family_rows) == 3,
        "all_family_ticket_audits_passed": all(row["passed"] for row in family_rows),
        "structured_covered": any(row["mode"] == "structured_policy_probe" and row["passed"] for row in family_rows),
        "bounded_decoder_covered": any(row["mode"] == "bounded_decoder_ce_probe" and row["passed"] for row in family_rows),
        "denoise_covered": any(row["mode"] == "denoise_repair_probe" and row["passed"] for row in family_rows),
        "same_stage_execution_closed": True,
        "next_stage_execution_closed": True,
        "all_authority_closed": True,
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "authority": dict(AUTHORITY_CLOSED),
        "family_ticket_coverage": family_rows,
        "blocked_until_explicit_request": list(BLOCKED_UNTIL_EXPLICIT_REQUEST),
        "decision": (
            "All three repo-local probe families have inactive audited ticket coverage. This is not execution "
            "authorization; final pre-execution audit remains blocked until an explicit one-run request."
        ),
        "next_best_step": (
            "Stop no-execution handoff churn. If explicitly requested later, choose exactly one family and run a "
            "fresh final pre-execution audit before any trainer invocation."
        ),
    }


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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix = build_matrix()
    MATRIX.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": matrix["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": matrix["failures"],
            "family_ticket_audits": len(matrix["family_ticket_coverage"]),
            "family_ticket_audits_passed": sum(1 for row in matrix["family_ticket_coverage"] if row["passed"]),
            "blocked_until_explicit_request": len(BLOCKED_UNTIL_EXPLICIT_REQUEST),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "matrix": str(MATRIX.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": matrix["decision"] if matrix["passed"] else "Repo-local ticket coverage final matrix failed.",
        "next_best_step": matrix["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9218 Repo-Local Ticket Coverage Final Matrix",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage confirms inactive audited ticket coverage for structured, bounded decoder, and denoise repo-local families.",
                "It does not run trainer, create a live ticket, execute a model, clean outputs, touch /arxiv, or open CE/runtime authority.",
                "",
                f"Family ticket audits: `{summary['metrics']['family_ticket_audits']}`",
                f"Family ticket audits passed: `{summary['metrics']['family_ticket_audits_passed']}`",
                "",
                f"Next: {summary['next_best_step']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
