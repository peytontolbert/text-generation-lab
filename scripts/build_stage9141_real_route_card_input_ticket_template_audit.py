#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9140_real_route_card_input_ticket_template import (
        build_ticket_template,
        validate_ticket_template,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9140_real_route_card_input_ticket_template import (  # type: ignore
        build_ticket_template,
        validate_ticket_template,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9141
NAME = "stage9141_real_route_card_input_ticket_template_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9140 = ROOT / "runs/summaries/stage9140_real_route_card_input_ticket_template.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_TICKET_TEMPLATE_AUDIT_STAGE9141.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_route_card_input_ticket_template_audit.json"

NEGATIVE_CASES = [
    "template_approved_for_execution",
    "max_rows_nonzero",
    "ticket_instance_materialized",
    "real_input_authorized",
    "dataset_rows_loaded",
    "route_cards_materialized",
    "opens_training",
    "opens_decoder_ce",
    "opens_runtime",
    "ticket_authority_open",
    "summary_authority_open",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9140) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_ticket_template(registry(latest=9139))
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "template_approved_for_execution":
            candidate["ticket_template"]["approved_for_execution"] = True
        elif name == "max_rows_nonzero":
            candidate["ticket_template"]["max_rows"] = 1
        elif name == "ticket_instance_materialized":
            candidate["metrics"]["ticket_instance_materialized"] = True
        elif name == "real_input_authorized":
            candidate["metrics"]["real_input_authorized_now"] = True
        elif name == "dataset_rows_loaded":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "route_cards_materialized":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "opens_training":
            candidate["metrics"]["training_authorized"] = True
        elif name == "opens_decoder_ce":
            candidate["metrics"]["decoder_ce_authorized"] = True
        elif name == "opens_runtime":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "ticket_authority_open":
            candidate["ticket_template"]["authority"]["model_execution_authorized_next"] = True
        elif name == "summary_authority_open":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate

    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_ticket_template(candidate, registry(latest=9999) if name == "bad_registry_frontier" else registry(latest=9139))
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9140)
    template_registry = registry(latest=9139)
    base = build_ticket_template(template_registry)
    base_failures = validate_ticket_template(base, template_registry)
    negatives = run_negative_cases()
    checks = {
        "source_stage9140_passed": source.get("passed") is True,
        "base_template_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "template_not_instance": base["ticket_template"]["ticket_kind"].endswith("TEMPLATE_NOT_INSTANCE"),
        "not_approved_for_execution": base["ticket_template"]["approved_for_execution"] is False,
        "max_rows_zero": base["ticket_template"]["max_rows"] == 0,
        "real_input_closed": base["metrics"]["real_input_authorized_now"] is False,
        "dataset_loading_closed": base["metrics"]["dataset_rows_loaded"] is False,
        "authority_closed": not any(base["authority"].values()) and not any(base["ticket_template"]["authority"].values()),
        "registry_frontier_stage9140": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9140,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    failures.extend(base_failures)
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
            "ticket_template_audited": True,
            "ticket_instance_materialized": False,
            "approved_for_execution": False,
            "real_input_authorized_now": False,
            "real_judge_rows_used": 0,
            "real_ranker_rows_used": 0,
            "real_route_cards_materialized": 0,
            "route_cards_materialized_now": False,
            "loss_mask_cards_materialized_now": False,
            "compiler_handoff_ready_now": False,
            "dataset_rows_loaded": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
            "cleanup_authorized_now": False,
        },
        "decision": "Audited the real route-card input ticket template and rejected executable ticket, row cap, real input, materialization, training, decoder CE, runtime, and authority mutations.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry_json = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = build_audit(registry_json)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Real route-card input ticket template audit failed.",
        "next_best_step": "Design a ticket-instance schema for a bounded real route-card input preflight; do not instantiate it yet.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9141 Real Route-Card Input Ticket Template Audit",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        f"Negative cases rejected: `{audit['metrics']['negative_cases_rejected']}/{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    rows = [row for row in registry_json.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry_json["rows"] = rows
    registry_json["passed"] = summary["passed"]
    registry_json["metrics"] = {
        **(registry_json.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry_json.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
