#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9104_trainer_execution_authorization_review_refresh import (
        REQUIRED_BEFORE_ANY_FUTURE_EXECUTION,
        build_card,
        validate_card,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9104_trainer_execution_authorization_review_refresh import (  # type: ignore
        REQUIRED_BEFORE_ANY_FUTURE_EXECUTION,
        build_card,
        validate_card,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9105
NAME = "stage9105_trainer_execution_authorization_review_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9104 = ROOT / "runs/summaries/stage9104_trainer_execution_authorization_review_refresh.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_EXECUTION_AUTHORIZATION_REVIEW_AUDIT_STAGE9105.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_execution_authorization_review_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9103) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_card(registry())
    cases: dict[str, dict[str, Any]] = {}

    same_stage = copy.deepcopy(base)
    same_stage["metrics"]["same_stage_execution_authorized"] = True
    cases["same_stage_execution_authorized"] = same_stage

    next_stage = copy.deepcopy(base)
    next_stage["metrics"]["next_stage_execution_authorized"] = True
    cases["next_stage_execution_authorized"] = next_stage

    trainer = copy.deepcopy(base)
    trainer["metrics"]["trainer_executed_now"] = True
    cases["trainer_executed_now"] = trainer

    contract = copy.deepcopy(base)
    contract["metrics"]["contract_only_invoked_now"] = True
    cases["contract_only_invoked_now"] = contract

    runtime_assertions = copy.deepcopy(base)
    runtime_assertions["metrics"]["runtime_assertions_executed_now"] = True
    cases["runtime_assertions_executed_now"] = runtime_assertions

    model_rows = copy.deepcopy(base)
    model_rows["metrics"]["model_input_rows_now"] = 1
    cases["model_input_rows_now"] = model_rows

    decoder_open = copy.deepcopy(base)
    decoder_open["metrics"]["decoder_ce_authorized"] = True
    cases["decoder_ce_authorized"] = decoder_open

    cleanup_open = copy.deepcopy(base)
    cleanup_open["metrics"]["cleanup_authorized_now"] = True
    cases["cleanup_authorized_now"] = cleanup_open

    missing_requirement = copy.deepcopy(base)
    missing_requirement["required_before_any_future_execution"].remove("final_pre_execution_audit_passed")
    cases["missing_future_execution_requirement"] = missing_requirement

    missing_blockers = copy.deepcopy(base)
    missing_blockers["current_blockers"] = []
    cases["current_blockers_missing"] = missing_blockers

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    return {
        name: {
            "failures": validate_card(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_card(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9104)
    base = build_card(registry())
    base_failures = validate_card(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9104_present": SOURCE_9104.exists(),
        "source_stage9104_passed": source.get("passed") is True,
        "base_review_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "future_execution_requirements_recorded": len(REQUIRED_BEFORE_ANY_FUTURE_EXECUTION) >= 7,
        "same_stage_execution_closed": base["metrics"]["same_stage_execution_authorized"] is False,
        "next_stage_execution_closed": base["metrics"]["next_stage_execution_authorized"] is False,
        "trainer_not_executed": base["metrics"]["trainer_executed_now"] is False,
        "contract_only_not_invoked": base["metrics"]["contract_only_invoked_now"] is False,
        "authority_closed": not any(base["authority"].values()),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "base_failures": base_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "negative_cases": len(negatives),
            "negative_cases_rejected": sum(1 for item in negatives.values() if item["rejected"]),
            "future_execution_requirements": len(REQUIRED_BEFORE_ANY_FUTURE_EXECUTION),
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "contract_only_invoked_now": False,
            "runtime_assertions_executed_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Trainer execution authorization review rejects same-stage execution, next-stage execution, trainer invocation, contract-only invocation, runtime assertion execution, model rows, decoder CE, cleanup, missing requirements, missing blockers, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9104, STAGE}:
        audit["failures"].append(f"unexpected_registry_frontier:{latest}")
        audit["passed"] = False
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Trainer execution authorization review audit failed.",
        "next_best_step": "Attach trainer execution authorization review controls to the central graph; keep execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9105 Trainer Execution Authorization Review Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9104 trainer execution authorization review with negative cases. No trainer, contract-only mode, runtime assertions, model rows, cleanup, or training are invoked.",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {**(registry_json.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
