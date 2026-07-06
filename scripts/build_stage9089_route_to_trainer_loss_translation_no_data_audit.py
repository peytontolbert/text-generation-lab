#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9088_route_to_trainer_loss_translation_no_data_design import (
        REQUIRED_INPUTS,
        TRANSLATION_OUTPUTS,
        build_design,
        validate_design,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9088_route_to_trainer_loss_translation_no_data_design import (  # type: ignore
        REQUIRED_INPUTS,
        TRANSLATION_OUTPUTS,
        build_design,
        validate_design,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9089
NAME = "stage9089_route_to_trainer_loss_translation_no_data_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9088 = ROOT / "runs/summaries/stage9088_route_to_trainer_loss_translation_no_data_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_TO_TRAINER_LOSS_TRANSLATION_NO_DATA_AUDIT_STAGE9089.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "route_to_trainer_loss_translation_no_data_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9087) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def validate_audit_candidate(candidate: dict[str, Any], registry_json: dict[str, Any]) -> list[str]:
    failures = validate_design(candidate, registry_json)
    for required in REQUIRED_INPUTS:
        if required not in candidate.get("required_inputs", []):
            failures.append(f"missing_required_input:{required}")
    for output in TRANSLATION_OUTPUTS:
        if output not in candidate.get("translation_outputs", []):
            failures.append(f"missing_translation_output:{output}")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry())
    cases: dict[str, dict[str, Any]] = {}

    missing_input = copy.deepcopy(base)
    missing_input["required_inputs"].remove("route_card_materialization_audit_output.json")
    cases["missing_route_card_materialization_audit_output"] = missing_input

    missing_output = copy.deepcopy(base)
    missing_output["translation_outputs"].remove("translation_negative_case_audit.json")
    cases["missing_translation_negative_case_audit_output"] = missing_output

    translation_ready = copy.deepcopy(base)
    translation_ready["metrics"]["translation_ready_now"] = True
    cases["translation_ready_now"] = translation_ready

    model_rows = copy.deepcopy(base)
    model_rows["metrics"]["model_input_rows_now"] = 1
    cases["model_input_rows_now"] = model_rows

    compiler_ready = copy.deepcopy(base)
    compiler_ready["metrics"]["compiler_handoff_ready_now"] = True
    cases["compiler_handoff_ready_now"] = compiler_ready

    trainer_ready = copy.deepcopy(base)
    trainer_ready["metrics"]["trainer_dry_run_ready_now"] = True
    cases["trainer_dry_run_ready_now"] = trainer_ready

    decoder_open = copy.deepcopy(base)
    decoder_open["metrics"]["decoder_ce_authorized"] = True
    cases["decoder_ce_authorized"] = decoder_open

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    return {
        name: {
            "failures": validate_audit_candidate(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_audit_candidate(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9088)
    base = build_design(registry())
    base_failures = validate_audit_candidate(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9088_present": SOURCE_9088.exists(),
        "source_stage9088_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "required_inputs_present": set(REQUIRED_INPUTS).issubset(set(base["required_inputs"])),
        "translation_outputs_present": set(TRANSLATION_OUTPUTS).issubset(set(base["translation_outputs"])),
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "translation_closed": base["metrics"]["translation_ready_now"] is False,
        "model_rows_zero": base["metrics"]["model_input_rows_now"] == 0,
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
            "translation_ready_now": False,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "trainer_dry_run_executed_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "route_cards_materialized_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "decision": "No-data route-to-trainer-loss translation design rejects missing inputs/outputs and premature translation, compiler handoff, trainer dry run, model rows, decoder CE, authority, and training.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    if int((registry_json.get("metrics") or {}).get("latest_stage", -1)) not in {9088, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Route-to-trainer-loss translation no-data audit failed.",
        "next_best_step": "Attach route-to-trainer-loss translation controls to the central graph; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9089 Route-To-Trainer-Loss Translation No-Data Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9088 no-data translation design with negative cases. No route cards, rows, compiler handoff, trainer execution, model forward, or training are authorized.",
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
