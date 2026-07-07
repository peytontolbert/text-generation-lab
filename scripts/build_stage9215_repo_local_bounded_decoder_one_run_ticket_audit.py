#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
    from build_stage9214_repo_local_bounded_decoder_one_run_ticket_design import (
        DENIED_NOW_OPERATIONS,
        MATRIX,
        SOURCE_8956,
        SOURCE_9213,
        audit_ticket,
        bounded_review,
        load_json,
    )
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from scripts.build_stage9214_repo_local_bounded_decoder_one_run_ticket_design import (  # type: ignore
        DENIED_NOW_OPERATIONS,
        MATRIX,
        SOURCE_8956,
        SOURCE_9213,
        audit_ticket,
        bounded_review,
        load_json,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9215
NAME = "stage9215_repo_local_bounded_decoder_one_run_ticket_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9214 = ROOT / "runs/summaries/stage9214_repo_local_bounded_decoder_one_run_ticket_design.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage9214_repo_local_bounded_decoder_one_run_ticket_design/repo_local_bounded_decoder_one_run_ticket_inactive.json"
SOURCE_AUDIT = ROOT / "runs/local/artifacts/stage9214_repo_local_bounded_decoder_one_run_ticket_design/repo_local_bounded_decoder_one_run_ticket_design_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REPO_LOCAL_BOUNDED_DECODER_ONE_RUN_TICKET_AUDIT_STAGE9215.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "repo_local_bounded_decoder_one_run_ticket_audit.json"


def negative_cases(ticket: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    mutated = copy.deepcopy(ticket)
    mutated["execution_authorized_now"] = True
    cases.append({"case": "execution_authorized_now_true", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["command_materialized"] = True
    cases.append({"case": "command_materialized_true", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["allowed_operations_now"] = ["run_trainer"]
    cases.append({"case": "allowed_operations_not_empty", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["denied_operations_now"] = [
        item for item in mutated.get("denied_operations_now", []) if item != "run_trainer"
    ]
    cases.append({"case": "run_trainer_not_denied", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["authority"] = dict(mutated.get("authority") or {})
    mutated["authority"]["model_execution_authorized_next"] = True
    cases.append({"case": "authority_open", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["future_output_dir"] = "/arxiv/blocked"
    cases.append({"case": "future_output_dir_arxiv", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["required_limits"] = dict(mutated.get("required_limits") or {})
    mutated["required_limits"]["denoise_weight"] = 1.0
    cases.append({"case": "denoise_weight_opened", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["required_limits"] = dict(mutated.get("required_limits") or {})
    mutated["required_limits"]["decoder_ce_weight"] = 0.0
    cases.append({"case": "decoder_ce_weight_closed_wrongly", "ticket": mutated})

    mutated = copy.deepcopy(ticket)
    mutated["required_limits"] = dict(mutated.get("required_limits") or {})
    mutated["required_limits"]["max_eval_rows"] = 32
    cases.append({"case": "eval_cap_too_large", "ticket": mutated})
    return cases


def run_negative_cases(ticket: dict[str, Any], source_9213: dict[str, Any], source_8956: dict[str, Any], matrix: dict[str, Any], review: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in negative_cases(ticket):
        audit = audit_ticket(case["ticket"], source_9213, source_8956, matrix, review)
        results.append(
            {
                "case": case["case"],
                "rejected": audit["passed"] is False,
                "failures": audit["failures"],
            }
        )
    return results


def build_audit() -> dict[str, Any]:
    source_9214 = load_json(SOURCE_9214)
    source_audit = load_json(SOURCE_AUDIT)
    source_9213 = load_json(SOURCE_9213)
    source_8956 = load_json(SOURCE_8956)
    matrix = load_json(MATRIX)
    ticket = load_json(SOURCE_TICKET)
    review = bounded_review(matrix)
    positive_audit = audit_ticket(ticket, source_9213, source_8956, matrix, review)
    negative_results = run_negative_cases(ticket, source_9213, source_8956, matrix, review)
    checks = {
        "source_stage9214_passed": source_9214.get("passed") is True,
        "source_ticket_exists": SOURCE_TICKET.is_file(),
        "source_audit_exists": SOURCE_AUDIT.is_file(),
        "source_audit_passed": source_audit.get("passed") is True,
        "positive_ticket_audit_passed": positive_audit.get("passed") is True,
        "all_negative_cases_rejected": all(item["rejected"] for item in negative_results),
        "ticket_inactive": ticket.get("ticket_status") == "DESIGN_ONLY_INACTIVE",
        "command_not_materialized": ticket.get("command_materialized") is False,
        "execution_not_authorized_now": ticket.get("execution_authorized_now") is False,
        "allowed_operations_empty": ticket.get("allowed_operations_now") == [],
        "run_trainer_denied": "run_trainer" in (ticket.get("denied_operations_now") or []),
        "walk_arxiv_denied": "walk_arxiv" in (ticket.get("denied_operations_now") or []),
        "all_authority_closed": not any((ticket.get("authority") or {}).values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "positive_audit": positive_audit,
        "negative_cases": negative_results,
        "denied_operations_now": list(DENIED_NOW_OPERATIONS),
        "decision": (
            "The inactive repo-local bounded-decoder one-run ticket design passes positive audit and rejects unsafe "
            "negative cases. This still creates no live ticket and authorizes no execution."
        ),
        "next_best_step": (
            "Bounded decoder now has an inactive audited ticket path. Next no-execution branch is the denoise "
            "dedicated one-run schema, or stop before final pre-execution audit until explicit execution is requested."
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
    audit = build_audit()
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": audit["failures"],
            "negative_cases": len(audit["negative_cases"]),
            "negative_cases_rejected": sum(1 for item in audit["negative_cases"] if item["rejected"]),
            "command_materialized": False,
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "cleanup_authorized_now": False,
        },
        "artifacts": {
            "audit": str(AUDIT.relative_to(ROOT)),
            "doc": str(DOC.relative_to(ROOT)),
        },
        "decision": audit["decision"] if audit["passed"] else "Repo-local bounded-decoder one-run ticket audit failed.",
        "next_best_step": audit["next_best_step"],
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text(
        "\n".join(
            [
                "# Stage9215 Repo-Local Bounded Decoder One-Run Ticket Audit",
                "",
                f"Passed: `{summary['passed']}`",
                "",
                "This stage audits the inactive Stage9214 bounded-decoder ticket design and negative cases.",
                "It does not create a live ticket, materialize an executable command, run trainer, clean outputs, or touch /arxiv.",
                "",
                f"Negative cases: `{summary['metrics']['negative_cases']}`",
                f"Negative cases rejected: `{summary['metrics']['negative_cases_rejected']}`",
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
