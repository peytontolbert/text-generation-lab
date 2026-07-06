#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
    from scripts.build_stage9057_long_context_route_card_schema_contract import (
        REQUIRED_FIELDS,
        REQUIRED_GATE_FIELDS,
        LOSS_KEYS,
        build_schema_contract,
    )
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore
    from build_stage9057_long_context_route_card_schema_contract import (  # type: ignore
        REQUIRED_FIELDS,
        REQUIRED_GATE_FIELDS,
        LOSS_KEYS,
        build_schema_contract,
    )

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9059
NAME = "stage9059_long_context_route_card_materialization_audit_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9058 = ROOT / "runs/summaries/stage9058_long_context_route_card_schema_graph_attachment.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_ROUTE_CARD_MATERIALIZATION_AUDIT_CONTRACT_STAGE9059.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "long_context_route_card_materialization_audit_contract.json"

REQUIRED_MATERIALIZATION_AUDITS = [
    "source_output_ticket_granted_and_scoped",
    "route_card_schema_v1_fields_present",
    "source_lineage_card_present",
    "dataset_junk_ood_ranker_card_present",
    "shortcut_baseline_card_present",
    "counterfactual_obligation_card_present",
    "split_overlap_card_present",
    "loss_mask_card_present_and_closed_by_default",
    "telemetry_contract_present",
    "compiler_ready_false_until_all_gates_pass",
]
NEGATIVE_CASES = {
    "missing_source_ticket": "source_output_ticket_granted",
    "missing_required_field": "route_card_id",
    "open_decoder_ce": "decoder_ce",
    "open_training_authority": "decoder_ce_training_authorized_next",
    "compiler_ready_without_gates": "compiler_ready",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_contract() -> dict[str, Any]:
    schema = build_schema_contract()
    return {
        "contract_name": "long_context_route_card_materialization_audit_v1",
        "status": "audit_contract_only_no_materialization",
        "schema_contract": schema["schema_name"],
        "required_fields": list(REQUIRED_FIELDS),
        "required_gate_fields": list(REQUIRED_GATE_FIELDS),
        "loss_keys": list(LOSS_KEYS),
        "required_materialization_audits": list(REQUIRED_MATERIALIZATION_AUDITS),
        "negative_cases": dict(NEGATIVE_CASES),
        "route_rows_materialized_now": False,
        "compiler_ready_rows_now": 0,
        "training_ready_rows_now": 0,
        "authority": dict(AUTHORITY_CLOSED),
    }


def sample_closed_card() -> dict[str, Any]:
    return {
        "route_card_id": "example_future_route_card_closed",
        "candidate_id": "candidate_placeholder",
        "source_ticket_id": "ticket_placeholder_not_granted",
        "source_lineage": {"source_ticket_granted": False},
        "route": "NEEDS_SOURCE_TICKET",
        "route_reasons": ["source_output_ticket_missing"],
        "required_gates_before_compiler": list(REQUIRED_GATE_FIELDS),
        "quality_signals": {},
        "risk_signals": {},
        "losses_enabled": {key: False for key in LOSS_KEYS},
        "compiler_ready": False,
        "training_ready": False,
        "model_input_ready": False,
        "authority": dict(AUTHORITY_CLOSED),
    }


def audit_route_card(card: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in card:
            failures.append(f"missing_field:{field}")
    gates = set(card.get("required_gates_before_compiler") or [])
    for gate in REQUIRED_GATE_FIELDS:
        if gate not in gates:
            failures.append(f"missing_gate:{gate}")
    losses = card.get("losses_enabled") or {}
    for key in LOSS_KEYS:
        if key not in losses:
            failures.append(f"missing_loss_key:{key}")
    if any(losses.values()):
        failures.append("loss_open")
    if any((card.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
        failures.append("authority_open")
    if card.get("compiler_ready") is True and not all(card.get("gate_status", {}).get(gate) is True for gate in REQUIRED_GATE_FIELDS):
        failures.append("compiler_ready_without_all_gates")
    if card.get("training_ready") is True:
        failures.append("training_ready_not_allowed_in_materialization_audit")
    return failures


def run_negative_cases() -> dict[str, Any]:
    base = sample_closed_card()
    cases: dict[str, dict[str, Any]] = {}
    missing_ticket = copy.deepcopy(base)
    missing_ticket["required_gates_before_compiler"] = [gate for gate in missing_ticket["required_gates_before_compiler"] if gate != "source_output_ticket_granted"]
    cases["missing_source_ticket"] = missing_ticket
    missing_field = copy.deepcopy(base)
    missing_field.pop("route_card_id")
    cases["missing_required_field"] = missing_field
    open_decoder = copy.deepcopy(base)
    open_decoder["losses_enabled"]["decoder_ce"] = True
    cases["open_decoder_ce"] = open_decoder
    open_auth = copy.deepcopy(base)
    open_auth["authority"]["decoder_ce_training_authorized_next"] = True
    cases["open_training_authority"] = open_auth
    ready = copy.deepcopy(base)
    ready["compiler_ready"] = True
    cases["compiler_ready_without_gates"] = ready
    return {name: {"failures": audit_route_card(card), "rejected": bool(audit_route_card(card))} for name, card in cases.items()}


def build_audit() -> dict[str, Any]:
    source = load_json(SOURCE_9058)
    contract = build_contract()
    closed_failures = audit_route_card(sample_closed_card())
    negatives = run_negative_cases()
    checks = {
        "source_stage9058_present": SOURCE_9058.exists(),
        "source_stage9058_passed": source.get("passed") is True,
        "contract_status_no_materialization": contract.get("status") == "audit_contract_only_no_materialization",
        "required_fields_recorded": set(REQUIRED_FIELDS).issubset(set(contract["required_fields"])),
        "required_gate_fields_recorded": set(REQUIRED_GATE_FIELDS).issubset(set(contract["required_gate_fields"])),
        "closed_sample_passes": closed_failures == [],
        "negative_cases_rejected": all(item["rejected"] for item in negatives.values()),
        "route_rows_not_materialized": contract["route_rows_materialized_now"] is False,
        "authority_closed": not any((contract.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED),
    }
    failures = [key for key, value in checks.items() if value is not True]
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "checks": checks,
        "failures": failures,
        "contract": contract,
        "closed_sample_failures": closed_failures,
        "negative_cases": negatives,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "required_materialization_audits": len(REQUIRED_MATERIALIZATION_AUDITS),
            "negative_cases": len(negatives),
            "route_rows_materialized_now": False,
            "compiler_ready_rows_now": 0,
            "training_ready_rows_now": 0,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
            "arxiv_write_authorized": False,
        },
        "decision": "Future long-context route-card materialization audit contract is defined; no route cards are materialized and compiler/training remain closed.",
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = build_audit()
    CONTRACT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "authority_rows": 0, "failures": audit["failures"], **audit["metrics"]},
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": audit["decision"] if audit["passed"] else "Long-context route-card materialization audit contract failed.",
        "next_best_step": "Continue trainer/compiler no-data recovery. Real route-card materialization still requires a granted source/output ticket and post-materialization audit.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9059 Long Context Route Card Materialization Audit Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the future materialization audit contract only. It materializes no route-card rows, reads no `/arxiv` data, compiles no manifest, and trains nothing.",
        "",
        f"Negative cases: `{audit['metrics']['negative_cases']}`",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ]) + "\n", encoding="utf-8")
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {
        **(registry.get("metrics") or {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": summary["next_best_step"],
        "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))),
        "registry_rows": len(rows),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
