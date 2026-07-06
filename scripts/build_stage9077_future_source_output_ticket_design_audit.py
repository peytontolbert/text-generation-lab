#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9076_future_source_output_ticket_design import build_contract, validate_contract
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9076_future_source_output_ticket_design import build_contract, validate_contract  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9077
NAME = "stage9077_future_source_output_ticket_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9076 = ROOT / "runs/summaries/stage9076_future_source_output_ticket_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_SOURCE_OUTPUT_TICKET_DESIGN_AUDIT_STAGE9077.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "future_source_output_ticket_design_audit.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9075) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_contract(registry())
    cases: dict[str, dict[str, Any]] = {}
    source_read = copy.deepcopy(base)
    source_read["metrics"]["source_metadata_read_now"] = True
    cases["source_metadata_read_now"] = source_read
    body_read = copy.deepcopy(base)
    body_read["metrics"]["repository_source_bodies_read_now"] = True
    cases["repository_source_bodies_read_now"] = body_read
    arxiv_write = copy.deepcopy(base)
    arxiv_write["metrics"]["arxiv_write_authorized"] = True
    cases["arxiv_write_authorized"] = arxiv_write
    delete_arxiv = copy.deepcopy(base)
    delete_arxiv["ticket_template"]["arxiv_policy"]["never_delete_arxiv"] = False
    cases["missing_never_delete_arxiv"] = delete_arxiv
    cleanup = copy.deepcopy(base)
    cleanup["metrics"]["cleanup_authorized_now"] = True
    cases["cleanup_authorized_now"] = cleanup
    training = copy.deepcopy(base)
    training["metrics"]["training_authorized"] = True
    cases["training_authorized"] = training
    open_authority = copy.deepcopy(base)
    open_authority["authority"]["model_execution_authorized_next"] = True
    cases["authority_open_model_execution"] = open_authority
    bad_frontier = copy.deepcopy(base)
    cases["unexpected_registry_frontier"] = bad_frontier
    return {
        name: {
            "failures": validate_contract(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry()),
            "rejected": bool(validate_contract(candidate, registry(latest=9999) if name == "unexpected_registry_frontier" else registry())),
        }
        for name, candidate in cases.items()
    }


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9076)
    base = build_contract(registry())
    base_failures = validate_contract(base, registry())
    negatives = run_negative_cases()
    checks = {
        "source_stage9076_present": SOURCE_9076.exists(),
        "source_stage9076_passed": source.get("passed") is True,
        "base_contract_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "arxiv_never_delete_recorded": base["ticket_template"]["arxiv_policy"]["never_delete_arxiv"] is True,
        "body_access_blocked": not any(base["ticket_template"]["body_access_policy"].values()),
        "current_access_closed": base["metrics"]["source_metadata_read_now"] is False and base["metrics"]["route_cards_materialized_now"] is False,
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
            "ticket_instantiated_now": False,
            "source_metadata_read_now": False,
            "row_bodies_read_now": False,
            "repository_source_bodies_read_now": False,
            "route_cards_materialized_now": False,
            "candidate_rows_materialized": 0,
            "arxiv_write_authorized": False,
            "cleanup_authorized_now": False,
            "training_authorized": False,
            "model_forward_attempted": False,
        },
        "decision": "Inactive source/output ticket negative cases are rejected. Current source metadata reads, body reads, /arxiv IO, cleanup, route-card materialization, mining, model execution, and training remain closed.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit()
    if int((registry_json.get("metrics") or {}).get("latest_stage", -1)) not in {9076, STAGE}:
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
        "decision": audit["decision"] if audit["passed"] else "Future source/output ticket design audit failed.",
        "next_best_step": "Attach the inactive source/output ticket design to the central graph, or reconcile the frontier; do not instantiate the ticket yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9077 Future Source/Output Ticket Design Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Audits the inactive source/output ticket schema with negative cases. The ticket is not instantiated and no access is granted.",
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
