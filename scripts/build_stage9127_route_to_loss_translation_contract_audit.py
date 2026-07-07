#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9126_route_to_loss_translation_contract_design import (
        FORBIDDEN_TRANSLATIONS,
        ROUTE_TO_LOSSES,
        build_contract,
        validate_contract,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9126_route_to_loss_translation_contract_design import (  # type: ignore
        FORBIDDEN_TRANSLATIONS,
        ROUTE_TO_LOSSES,
        build_contract,
        validate_contract,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9127
NAME = "stage9127_route_to_loss_translation_contract_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9126 = ROOT / "runs/summaries/stage9126_route_to_loss_translation_contract_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ROUTE_TO_LOSS_TRANSLATION_CONTRACT_AUDIT_STAGE9127.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "route_to_loss_translation_contract_audit.json"

REJECT_METRICS = [
    "route_cards_materialized_now",
    "route_to_loss_translation_ready_now",
    "loss_mask_cards_materialized_now",
    "compiler_handoff_ready_now",
    "dataset_rows_loaded",
    "repository_source_bodies_loaded",
    "trainer_executed_now",
    "model_forward_attempted",
    "training_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "runtime_authorized_flag",
    "network_upload_performed",
    "cleanup_authorized_now",
]

FORBIDDEN_DECODER_CE_ROUTES = [
    "KEEP_STRUCTURED",
    "HOLD_LONG_OUTPUT",
    "USE_AS_NEGATIVE",
    "NEEDS_RETRIEVAL",
    "QUARANTINE_LABEL_CONFLICT",
    "DROP_DUPLICATE",
    "NEEDS_HUMAN_REVIEW",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9125) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def semantic_failures(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    route_to_losses = contract.get("route_to_losses", {})
    if "decoder_ce" not in route_to_losses.get("KEEP_BOUNDED_DECODER", []):
        failures.append("bounded_decoder_missing_decoder_ce")
    for route in FORBIDDEN_DECODER_CE_ROUTES:
        if "decoder_ce" in route_to_losses.get(route, []):
            failures.append(f"forbidden_decoder_ce_route:{route}")
    for route in ["QUARANTINE_LABEL_CONFLICT", "DROP_DUPLICATE", "NEEDS_HUMAN_REVIEW"]:
        if route_to_losses.get(route) != []:
            failures.append(f"quarantine_route_has_loss:{route}")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = build_contract(registry())
    cases: dict[str, dict[str, Any]] = {}
    for metric in REJECT_METRICS:
        candidate = copy.deepcopy(base)
        candidate["metrics"][metric] = True
        cases[metric] = candidate

    missing_route = copy.deepcopy(base)
    del missing_route["route_to_losses"]["KEEP_BOUNDED_DECODER"]
    cases["missing_keep_bounded_decoder_translation"] = missing_route

    missing_forbidden = copy.deepcopy(base)
    missing_forbidden["forbidden_translations"].remove("HOLD_LONG_OUTPUT_to_decoder_ce")
    cases["missing_hold_long_output_forbidden_translation"] = missing_forbidden

    bad_holdout = copy.deepcopy(base)
    bad_holdout["route_to_losses"]["HOLD_LONG_OUTPUT"].append("decoder_ce")
    cases["hold_long_output_maps_to_decoder_ce"] = bad_holdout

    bad_quarantine = copy.deepcopy(base)
    bad_quarantine["route_to_losses"]["QUARANTINE_LABEL_CONFLICT"].append("action_ce")
    cases["quarantine_maps_to_loss"] = bad_quarantine

    authority_open = copy.deepcopy(base)
    authority_open["authority"]["model_execution_authorized_next"] = True
    cases["authority_open"] = authority_open

    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_contract(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())
        failures.extend(semantic_failures(candidate))
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9126)
    base = build_contract(registry())
    base_failures = validate_contract(base, registry()) + semantic_failures(base)
    negatives = run_negative_cases()
    checks = {
        "source_stage9126_present": SOURCE_9126.exists(),
        "source_stage9126_passed": source.get("passed") is True,
        "base_contract_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "route_to_losses_recorded": len(ROUTE_TO_LOSSES) >= 9,
        "forbidden_translations_recorded": len(FORBIDDEN_TRANSLATIONS) >= 8,
        "decoder_ce_only_on_bounded_decoder_route": not any("decoder_ce" in base["route_to_losses"].get(route, []) for route in FORBIDDEN_DECODER_CE_ROUTES),
        "quarantine_routes_have_no_losses": all(base["route_to_losses"].get(route) == [] for route in ["QUARANTINE_LABEL_CONFLICT", "DROP_DUPLICATE", "NEEDS_HUMAN_REVIEW"]),
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
            "routes": len(ROUTE_TO_LOSSES),
            "forbidden_translations": len(FORBIDDEN_TRANSLATIONS),
            "route_cards_materialized_now": False,
            "route_to_loss_translation_ready_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Route-to-loss translation contract audit rejects unsafe mappings, especially decoder CE on non-bounded routes, quarantine routes with losses, materialization, compiler handoff, trainer/model paths, training, runtime, upload, cleanup, authority, and bad frontier.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    latest = int((registry_json.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {9126, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Route-to-loss translation contract audit failed.",
        "next_best_step": "Recover loss-mask card schema; do not materialize real loss masks yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9127 Route-To-Loss Translation Contract Audit",
        "",
        f"Passed: `{summary['passed']}`",
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
