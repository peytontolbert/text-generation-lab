#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9057
NAME = "stage9057_long_context_route_card_schema_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_9056 = ROOT / "runs/summaries/stage9056_long_context_synthetic_route_card_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LONG_CONTEXT_ROUTE_CARD_SCHEMA_CONTRACT_STAGE9057.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CONTRACT = OUT_DIR / "long_context_route_card_schema_contract.json"

ROUTES = [
    "CANDIDATE_REVIEW_ONLY",
    "NEEDS_HUMAN_REVIEW",
    "NEEDS_SOURCE_TICKET",
    "NEEDS_JUDGE",
    "NEEDS_SHORTCUT_AUDIT",
    "KEEP_STRUCTURED_AFTER_GATES",
    "HOLD_LONG_OUTPUT",
    "DROP_NOISY_SOURCE",
]
REQUIRED_FIELDS = [
    "route_card_id",
    "candidate_id",
    "source_ticket_id",
    "source_lineage",
    "route",
    "route_reasons",
    "required_gates_before_compiler",
    "quality_signals",
    "risk_signals",
    "losses_enabled",
    "compiler_ready",
    "training_ready",
    "model_input_ready",
    "authority",
]
REQUIRED_GATE_FIELDS = [
    "source_output_ticket_granted",
    "source_lineage_card",
    "dataset_junk_ood_ranker_card",
    "shortcut_baseline_audit",
    "counterfactual_obligation_card",
    "split_overlap_audit",
    "loss_mask_card",
    "telemetry_contract",
]
LOSS_KEYS = ["structured_aux_ce", "decoder_ce", "denoise_ce", "retrieval_loss", "runtime_reward"]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_schema_contract() -> dict[str, Any]:
    return {
        "schema_name": "long_context_route_card_v1",
        "status": "metadata_schema_only_no_rows",
        "allowed_routes": list(ROUTES),
        "required_fields": list(REQUIRED_FIELDS),
        "required_gate_fields": list(REQUIRED_GATE_FIELDS),
        "loss_keys": list(LOSS_KEYS),
        "closed_default_loss_mask": {key: False for key in LOSS_KEYS},
        "authority": dict(AUTHORITY_CLOSED),
        "compiler_ready_rule": "compiler_ready may become true only after all required gates pass, authority remains closed for training, and losses_enabled is explicitly audited",
        "decoder_ce_rule": "decoder_ce remains false unless a future bounded-decoder ticket, target-budget audit, judge card, and loss-mask audit pass",
        "denoise_ce_rule": "denoise_ce remains false unless a separate repair-denoise ticket and verifier-feedback manifest pass",
    }


def audit_contract(contract: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if contract.get("status") != "metadata_schema_only_no_rows":
        failures.append("status_not_schema_only")
    if not set(REQUIRED_FIELDS).issubset(set(contract.get("required_fields") or [])):
        failures.append("missing_required_fields")
    if not set(REQUIRED_GATE_FIELDS).issubset(set(contract.get("required_gate_fields") or [])):
        failures.append("missing_required_gate_fields")
    if set(contract.get("loss_keys") or []) != set(LOSS_KEYS):
        failures.append("loss_keys_mismatch")
    if any((contract.get("closed_default_loss_mask") or {}).values()):
        failures.append("default_loss_open")
    if any((contract.get("authority") or {}).get(key) for key in AUTHORITY_CLOSED):
        failures.append("authority_open")
    source = load_json(SOURCE_9056)
    if source.get("passed") is not True:
        failures.append("source_stage9056_not_passed")
    return failures


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    contract = build_schema_contract()
    failures = audit_contract(contract)
    CONTRACT.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            **dict(AUTHORITY_CLOSED),
            "authority_rows": 0,
            "failures": failures,
            "allowed_routes": len(ROUTES),
            "required_fields": len(REQUIRED_FIELDS),
            "required_gate_fields": len(REQUIRED_GATE_FIELDS),
            "loss_keys": len(LOSS_KEYS),
            "schema_only_no_rows": True,
            "route_rows_materialized_now": False,
            "training_authorized": False,
            "model_execution_attempted": False,
            "arxiv_read_authorized_now": False,
        },
        "artifacts": {"contract": str(CONTRACT.relative_to(ROOT))},
        "decision": "Long-context route-card schema contract is defined as metadata-only; no rows are materialized and no compiler/training authority opens.",
        "next_best_step": "Attach the route-card schema contract to the central graph or continue trainer/compiler no-data recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9057 Long Context Route Card Schema Contract",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "This stage defines the metadata-only route-card schema for future granted long-context source tickets. It materializes no real route rows, reads no `/arxiv` data, compiles no manifest, and trains nothing.",
        "",
        f"Allowed routes: `{len(ROUTES)}`",
        f"Required fields: `{len(REQUIRED_FIELDS)}`",
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
