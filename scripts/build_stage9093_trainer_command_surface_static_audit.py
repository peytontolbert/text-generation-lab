#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9092_trainer_command_surface_static_refresh import (
        REQUIRED_FLAGS,
        REQUIRED_GUARD_TERMS,
        REQUIRED_MODES,
        build_card,
        validate_card,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9092_trainer_command_surface_static_refresh import (  # type: ignore
        REQUIRED_FLAGS,
        REQUIRED_GUARD_TERMS,
        REQUIRED_MODES,
        build_card,
        validate_card,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9093
NAME = "stage9093_trainer_command_surface_static_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9092 = ROOT / "runs/summaries/stage9092_trainer_command_surface_static_refresh.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINER_COMMAND_SURFACE_STATIC_AUDIT_STAGE9093.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "trainer_command_surface_static_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9091) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def validate_audit_candidate(candidate: dict[str, Any], registry_json: dict[str, Any]) -> list[str]:
    failures = validate_card(candidate, registry_json)
    for flag in REQUIRED_FLAGS:
        if flag not in candidate.get("required_flags", []):
            failures.append(f"missing_required_flag:{flag}")
    for mode in REQUIRED_MODES:
        if mode not in candidate.get("required_modes", []):
            failures.append(f"missing_required_mode:{mode}")
    for term in REQUIRED_GUARD_TERMS:
        if term not in candidate.get("required_guard_terms", []):
            failures.append(f"missing_required_guard_term:{term}")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_card(registry())
    cases: dict[str, dict[str, Any]] = {}

    missing_flag = copy.deepcopy(base)
    missing_flag["required_flags"].remove("--manifest")
    cases["missing_manifest_flag"] = missing_flag

    missing_mode = copy.deepcopy(base)
    missing_mode["required_modes"].remove("bounded_decoder_ce_probe")
    cases["missing_bounded_decoder_mode"] = missing_mode

    missing_guard = copy.deepcopy(base)
    missing_guard["required_guard_terms"].remove("safe_cleanup_checkpoints")
    cases["missing_safe_cleanup_guard"] = missing_guard

    trainer_executed = copy.deepcopy(base)
    trainer_executed["metrics"]["trainer_executed_now"] = True
    cases["trainer_executed_now"] = trainer_executed

    contract_invoked = copy.deepcopy(base)
    contract_invoked["metrics"]["contract_only_invoked_now"] = True
    cases["contract_only_invoked_now"] = contract_invoked

    model_rows = copy.deepcopy(base)
    model_rows["metrics"]["model_input_rows_now"] = 1
    cases["model_input_rows_now"] = model_rows

    route_ready = copy.deepcopy(base)
    route_ready["metrics"]["route_to_loss_translation_ready_now"] = True
    cases["route_to_loss_translation_ready_now"] = route_ready

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
    source = load_json(SOURCE_9092)
    base = build_card(registry())
    base_failures = validate_audit_candidate(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9092_present": SOURCE_9092.exists(),
        "source_stage9092_passed": source.get("passed") is True,
        "base_static_card_passes": base_failures == [],
        "required_flags_present": set(REQUIRED_FLAGS).issubset(set(base["required_flags"])),
        "required_modes_present": set(REQUIRED_MODES).issubset(set(base["required_modes"])),
        "required_guard_terms_present": set(REQUIRED_GUARD_TERMS).issubset(set(base["required_guard_terms"])),
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "trainer_static_only": base["metrics"]["trainer_static_inspection_only"] is True,
        "trainer_not_executed": base["metrics"]["trainer_executed_now"] is False,
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
            "trainer_static_inspection_only": True,
            "trainer_executed_now": False,
            "trainer_dry_run_ready_now": False,
            "contract_only_invoked_now": False,
            "route_to_loss_translation_ready_now": False,
            "model_input_rows_now": 0,
            "candidate_rows_materialized": 0,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Trainer command surface static refresh rejects missing required flags, modes, guard terms, premature trainer invocation, route-to-loss translation, model input rows, decoder CE, authority, and training.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    if int((registry_json.get("metrics") or {}).get("latest_stage", -1)) not in {9092, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Trainer command surface static audit failed.",
        "next_best_step": "Attach trainer command surface static controls to the central graph; do not execute trainer or load rows.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9093 Trainer Command Surface Static Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the Stage9092 static trainer command surface with negative cases. The trainer is not invoked.",
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
