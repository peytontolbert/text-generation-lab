#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9080_no_data_route_card_materialization_audit_instance_design import (
        build_design,
        validate_design,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9080_no_data_route_card_materialization_audit_instance_design import (  # type: ignore
        build_design,
        validate_design,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9081
NAME = "stage9081_no_data_route_card_materialization_audit_instance_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9080 = ROOT / "runs/summaries/stage9080_no_data_route_card_materialization_audit_instance_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_DATA_ROUTE_CARD_MATERIALIZATION_AUDIT_INSTANCE_AUDIT_STAGE9081.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "no_data_route_card_materialization_audit_instance_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9079) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry())
    cases: dict[str, dict[str, Any]] = {}
    instance = copy.deepcopy(base)
    instance["metrics"]["instance_instantiated_now"] = True
    cases["instance_instantiated_now"] = instance
    source_ticket = copy.deepcopy(base)
    source_ticket["metrics"]["source_output_ticket_instantiated_now"] = True
    cases["source_output_ticket_instantiated_now"] = source_ticket
    metadata = copy.deepcopy(base)
    metadata["metrics"]["source_metadata_read_now"] = True
    cases["source_metadata_read_now"] = metadata
    route_cards = copy.deepcopy(base)
    route_cards["metrics"]["route_cards_materialized_now"] = True
    cases["route_cards_materialized_now"] = route_cards
    compiler = copy.deepcopy(base)
    compiler["metrics"]["compiler_handoff_ready_now"] = True
    cases["compiler_handoff_ready_now"] = compiler
    trainer = copy.deepcopy(base)
    trainer["metrics"]["trainer_dry_run_ready_now"] = True
    cases["trainer_dry_run_ready_now"] = trainer
    open_template = copy.deepcopy(base)
    open_template["instance_template"]["closed_now"]["row_bodies_read_now"] = True
    cases["template_closed_now_open"] = open_template
    open_authority = copy.deepcopy(base)
    open_authority["authority"]["model_execution_authorized_next"] = True
    cases["authority_open_model_execution"] = open_authority
    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier
    return {
        name: {
            "failures": validate_design(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_design(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9080)
    base = build_design(registry())
    base_failures = validate_design(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9080_present": SOURCE_9080.exists(),
        "source_stage9080_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "instance_closed_now": not any((base.get("instance_template") or {}).get("closed_now", {}).values()),
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
            "instance_instantiated_now": False,
            "source_output_ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "compiler_handoff_ready_now": False,
            "trainer_dry_run_ready_now": False,
            "training_authorized": False,
            "model_forward_attempted": False,
        },
        "decision": "Inactive route-card materialization audit instance negative cases are rejected. No source/output ticket, metadata read, route-card materialization, compiler handoff, trainer dry run, model execution, or training is authorized.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    if int((registry_json.get("metrics") or {}).get("latest_stage", -1)) not in {9080, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "No-data route-card materialization audit instance audit failed.",
        "next_best_step": "Attach the inactive route-card materialization audit instance to the central graph, or reconcile the frontier; do not instantiate it yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9081 No-Data Route-Card Materialization Audit Instance Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the inactive Stage9080 route-card materialization audit instance with negative cases. No instance is executed or materialized.",
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
