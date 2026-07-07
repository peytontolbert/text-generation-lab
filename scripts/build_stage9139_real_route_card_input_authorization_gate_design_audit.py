#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.build_stage9138_real_route_card_input_authorization_gate_design import (
        FORBIDDEN_INPUT_FIELDS,
        REQUIRED_PREFLIGHT_CHECKS,
        REQUIRED_TICKET_FIELDS,
        build_design,
        validate_design,
    )
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from build_stage9138_real_route_card_input_authorization_gate_design import (  # type: ignore
        FORBIDDEN_INPUT_FIELDS,
        REQUIRED_PREFLIGHT_CHECKS,
        REQUIRED_TICKET_FIELDS,
        build_design,
        validate_design,
    )
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9139
NAME = "stage9139_real_route_card_input_authorization_gate_design_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9138 = ROOT / "runs/summaries/stage9138_real_route_card_input_authorization_gate_design.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REAL_ROUTE_CARD_INPUT_AUTHORIZATION_GATE_DESIGN_AUDIT_STAGE9139.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "real_route_card_input_authorization_gate_design_audit.json"

NEGATIVE_CASES = [
    "missing_judge_ticket_field",
    "missing_ranker_ticket_field",
    "missing_arxiv_preflight",
    "missing_source_body_preflight",
    "missing_forbidden_decoder_target",
    "authorizes_real_input",
    "loads_dataset_rows",
    "materializes_route_cards",
    "opens_training",
    "opens_runtime",
    "opens_authority",
    "bad_registry_frontier",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def registry(latest: int = 9138) -> dict[str, Any]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def run_negative_cases() -> dict[str, Any]:
    base = build_design(registry(latest=9137))
    cases: dict[str, dict[str, Any]] = {}
    for name in NEGATIVE_CASES:
        candidate = copy.deepcopy(base)
        if name == "missing_judge_ticket_field":
            candidate["required_ticket_fields"].remove("judge_rows_path")
        elif name == "missing_ranker_ticket_field":
            candidate["required_ticket_fields"].remove("junk_ranker_rows_path")
        elif name == "missing_arxiv_preflight":
            candidate["required_preflight_checks"].remove("no_arxiv_path_without_separate_authorization")
        elif name == "missing_source_body_preflight":
            candidate["required_preflight_checks"].remove("no_source_body_fields_present")
        elif name == "missing_forbidden_decoder_target":
            candidate["forbidden_input_fields"].remove("decoder_target")
        elif name == "authorizes_real_input":
            candidate["metrics"]["real_input_authorized_now"] = True
        elif name == "loads_dataset_rows":
            candidate["metrics"]["dataset_rows_loaded"] = True
        elif name == "materializes_route_cards":
            candidate["metrics"]["route_cards_materialized_now"] = True
        elif name == "opens_training":
            candidate["metrics"]["training_authorized"] = True
        elif name == "opens_runtime":
            candidate["metrics"]["runtime_authorized_flag"] = True
        elif name == "opens_authority":
            candidate["authority"]["model_execution_authorized_next"] = True
        cases[name] = candidate
    audited: dict[str, Any] = {}
    for name, candidate in cases.items():
        failures = validate_design(candidate, registry(latest=9999) if name == "bad_registry_frontier" else registry(latest=9137))
        audited[name] = {"failures": failures, "rejected": bool(failures)}
    return audited


def build_audit(registry_card: dict[str, Any] | None = None) -> dict[str, Any]:
    registry_card = registry_card or registry()
    source = load_json(SOURCE_9138)
    design_registry = registry(latest=9137)
    base = build_design(design_registry)
    base_failures = validate_design(base, design_registry)
    negatives = run_negative_cases()
    checks = {
        "source_stage9138_passed": source.get("passed") is True,
        "base_design_passes": base_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "required_ticket_fields_complete": set(REQUIRED_TICKET_FIELDS).issubset(set(base["required_ticket_fields"])),
        "required_preflight_checks_complete": set(REQUIRED_PREFLIGHT_CHECKS).issubset(set(base["required_preflight_checks"])),
        "forbidden_input_fields_complete": set(FORBIDDEN_INPUT_FIELDS).issubset(set(base["forbidden_input_fields"])),
        "registry_frontier_stage9138": int((registry_card.get("metrics") or {}).get("latest_stage", -1)) == 9138,
        "authority_counts_zero": not any(((registry_card.get("metrics") or {}).get("authority_counts") or {}).get(key, 0) for key in AUTHORITY_CLOSED),
        "real_input_closed": base["metrics"]["real_input_authorized_now"] is False,
        "dataset_loading_closed": base["metrics"]["dataset_rows_loaded"] is False,
        "authority_closed": not any(base["authority"].values()),
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
        "decision": "Audited real route-card input authorization gate design and rejected missing fields, missing preflights, missing forbidden fields, real input authorization, dataset loading, route-card materialization, training, runtime, and authority openings.",
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
        "decision": audit["decision"] if audit["passed"] else "Real route-card input authorization gate design audit failed.",
        "next_best_step": "Create a real route-card input ticket template; keep real input loading closed until explicit ticket instance approval.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9139 Real Route-Card Input Authorization Gate Design Audit",
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
