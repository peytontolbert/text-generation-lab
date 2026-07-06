#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9065_trainer_dry_run_input_refresh_after_long_context_controls import (
        ADDITIONAL_ASSERTIONS,
        REQUIRED_LONG_CONTEXT_INPUTS,
        build_design,
        validate_design,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9065_trainer_dry_run_input_refresh_after_long_context_controls import (  # type: ignore
        ADDITIONAL_ASSERTIONS,
        REQUIRED_LONG_CONTEXT_INPUTS,
        build_design,
        validate_design,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9066
NAME = "stage9066_trainer_dry_run_input_negative_case_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9065 = ROOT / "runs/summaries/stage9065_trainer_dry_run_input_refresh_after_long_context_controls.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_DRY_RUN_INPUT_NEGATIVE_CASE_AUDIT_STAGE9066.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_PATH = OUT_DIR / "trainer_dry_run_input_negative_case_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9064) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry())
    cases: dict[str, dict[str, Any]] = {}
    missing_handoff = copy.deepcopy(base)
    missing_handoff["future_required_inputs"].remove("long_context_compiler_handoff_blocker_audit.json")
    cases["missing_long_context_handoff_input"] = missing_handoff
    missing_loss = copy.deepcopy(base)
    missing_loss["future_required_inputs"].remove("long_context_loss_mask_compiler_preflight.json")
    cases["missing_long_context_loss_mask_input"] = missing_loss
    missing_assertion = copy.deepcopy(base)
    missing_assertion["required_assertions"].remove("route_to_trainer_loss_translation_blocks_decoder_denoise_runtime")
    cases["missing_route_to_trainer_loss_assertion"] = missing_assertion
    executed = copy.deepcopy(base)
    executed["metrics"]["trainer_dry_run_executed_now"] = True
    cases["trainer_dry_run_executed_now"] = executed
    forward = copy.deepcopy(base)
    forward["metrics"]["model_forward_attempted"] = True
    cases["model_forward_attempted"] = forward
    weights = copy.deepcopy(base)
    weights["metrics"]["model_weights_loaded"] = True
    cases["model_weights_loaded"] = weights
    open_authority = copy.deepcopy(base)
    open_authority["authority"]["model_execution_authorized_next"] = True
    cases["authority_open_model_execution"] = open_authority
    training = copy.deepcopy(base)
    training["metrics"]["training_authorized"] = True
    cases["training_authorized"] = training
    wrong_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = wrong_frontier
    return {
        name: {
            "failures": validate_design(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_design(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9065)
    base = build_design(registry())
    base_failures = validate_design(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9065_present": SOURCE_9065.exists(),
        "source_stage9065_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "all_long_context_inputs_covered": set(REQUIRED_LONG_CONTEXT_INPUTS).issubset(set(base["future_required_inputs"])),
        "all_long_context_assertions_covered": set(ADDITIONAL_ASSERTIONS).issubset(set(base["required_assertions"])),
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "no_trainer_execution": base["metrics"].get("trainer_dry_run_executed_now") is False,
        "no_model_forward": base["metrics"].get("model_forward_attempted") is False,
        "authority_closed": not any(AUTHORITY_CLOSED.values()),
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
            "trainer_dry_run_executed_now": False,
            "model_forward_attempted": False,
            "model_weights_loaded": False,
            "training_authorized": False,
            "model_execution_attempted": False,
        },
        "decision": "Trainer dry-run input negative cases are rejected; missing long-context inputs, missing loss-translation assertions, execution flags, and authority reopen attempts remain blocked.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    AUDIT_PATH.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT_PATH.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Trainer dry-run input negative-case audit failed.",
        "next_best_step": "Continue no-data recovery by attaching Stage9065-9066 trainer dry-run controls to the central graph or refreshing trainer docs; do not execute trainer.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9066 Trainer Dry-Run Input Negative-Case Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Negative cases for the Stage9065 trainer dry-run input contract are rejected. This stage does not invoke the trainer, load rows, or authorize model execution.",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        f"Rejected: `{audit['metrics']['negative_cases_rejected']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
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
