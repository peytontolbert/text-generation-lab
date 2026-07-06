#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9084_trainer_dry_run_input_completeness_after_route_card_graph import (
        ADDITIONAL_REQUIRED_INPUTS,
        REQUIRED_BLOCKING_ASSERTIONS,
        build_checklist,
        validate_checklist,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9084_trainer_dry_run_input_completeness_after_route_card_graph import (  # type: ignore
        ADDITIONAL_REQUIRED_INPUTS,
        REQUIRED_BLOCKING_ASSERTIONS,
        build_checklist,
        validate_checklist,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9085
NAME = "stage9085_trainer_dry_run_input_completeness_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9084 = ROOT / "runs/summaries/stage9084_trainer_dry_run_input_completeness_after_route_card_graph.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_COMPLETENESS_AUDIT_STAGE9085.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_dry_run_input_completeness_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9083) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_checklist(registry())
    cases: dict[str, dict[str, Any]] = {}

    missing_ticket = copy.deepcopy(base)
    missing_ticket["future_required_inputs"].remove("source_output_ticket_authorization_card.json")
    cases["missing_source_output_ticket_authorization"] = missing_ticket

    missing_route_audit = copy.deepcopy(base)
    missing_route_audit["future_required_inputs"].remove("route_card_materialization_audit_output.json")
    cases["missing_route_card_materialization_audit_output"] = missing_route_audit

    missing_block = copy.deepcopy(base)
    missing_block["required_blocking_assertions"].remove("trainer_dry_run_blocked_until_route_card_audit_passes")
    cases["missing_trainer_blocking_assertion"] = missing_block

    trainer_ready = copy.deepcopy(base)
    trainer_ready["metrics"]["trainer_dry_run_ready_now"] = True
    cases["trainer_dry_run_ready_now"] = trainer_ready

    row_materialized = copy.deepcopy(base)
    row_materialized["metrics"]["candidate_rows_materialized"] = 1
    cases["candidate_rows_materialized"] = row_materialized

    route_cards = copy.deepcopy(base)
    route_cards["metrics"]["route_cards_materialized_now"] = True
    cases["route_cards_materialized_now"] = route_cards

    arxiv_open = copy.deepcopy(base)
    arxiv_open["metrics"]["arxiv_read_authorized_for_compiler"] = True
    cases["arxiv_read_authorized_for_compiler"] = arxiv_open

    open_authority = copy.deepcopy(base)
    open_authority["authority"]["decoder_ce_training_authorized_next"] = True
    cases["authority_open_decoder_ce"] = open_authority

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    return {
        name: {
            "failures": validate_checklist(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_checklist(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9084)
    base = build_checklist(registry())
    base_failures = validate_checklist(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9084_present": SOURCE_9084.exists(),
        "source_stage9084_passed": source.get("passed") is True,
        "base_checklist_passes": base_failures == [],
        "additional_inputs_present": set(ADDITIONAL_REQUIRED_INPUTS).issubset(set(base["future_required_inputs"])),
        "blocking_assertions_present": set(REQUIRED_BLOCKING_ASSERTIONS).issubset(set(base["required_blocking_assertions"])),
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "trainer_closed": base["metrics"]["trainer_dry_run_ready_now"] is False and base["metrics"]["trainer_dry_run_executed_now"] is False,
        "no_rows_or_route_cards_materialized": base["metrics"]["candidate_rows_materialized"] == 0 and base["metrics"]["route_cards_materialized_now"] is False,
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
            "additional_inputs_checked": len(ADDITIONAL_REQUIRED_INPUTS),
            "blocking_assertions_checked": len(REQUIRED_BLOCKING_ASSERTIONS),
            "trainer_dry_run_ready_now": False,
            "trainer_dry_run_executed_now": False,
            "source_output_ticket_instantiated_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "model_forward_attempted": False,
            "training_ready": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Trainer dry-run input completeness checklist passes the no-execution audit and rejects missing control inputs, premature row/route-card materialization, /arxiv compiler access, trainer readiness, and open authority.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    if int((registry_json.get("metrics") or {}).get("latest_stage", -1)) not in {9084, STAGE}:
        audit["failures"].append(f"unexpected_registry_frontier:{(registry_json.get('metrics') or {}).get('latest_stage')}")
        audit["passed"] = False
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Trainer dry-run input completeness audit failed.",
        "next_best_step": "Attach the trainer dry-run input completeness controls to the central graph; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9085 Trainer Dry-Run Input Completeness Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9084 checklist with negative cases. No trainer, rows, source bodies, route cards, compiler handoff, model forward, decoder CE, denoise CE, runtime, or /arxiv IO are authorized.",
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
