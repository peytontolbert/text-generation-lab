#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

try:
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields
except ModuleNotFoundError:  # pragma: no cover
    from diagnostic_ticket_contract import AUTHORITY_CLOSED, audit_diagnostic_ticket_fields  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8915
NAME = "stage8915_future_ticket_pre_execution_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SOURCE_SUMMARY = ROOT / "runs/summaries/stage8913_future_live_ticket_builder_skeleton.json"
SOURCE_TICKET = ROOT / "runs/local/artifacts/stage8913_future_live_ticket_builder_skeleton/future_stage8890_live_ticket_template_inactive.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FUTURE_TICKET_PRE_EXECUTION_AUDIT_STAGE8915.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT = OUT_DIR / "future_ticket_pre_execution_audit.json"

REQUIRED_LIMITS = {
    "mode": "structured_policy_probe",
    "max_train_rows": 32,
    "max_eval_rows": 16,
    "max_strict_rows": 16,
    "max_steps": 8,
    "batch_size": 2,
    "max_encoder_tokens": 256,
    "max_decoder_tokens": 64,
    "structured_aux_weight": 1.0,
    "decoder_ce_weight": 0.0,
    "denoise_weight": 0.0,
    "runtime": False,
}

REQUIRED_DENIED_OPERATIONS = {
    "load_checkpoint",
    "run_forward",
    "decode_tokens",
    "write_model_output_artifact",
    "compute_decoder_ce",
    "compute_denoise_ce",
    "run_runtime",
    "call_gemma",
    "score_output",
    "emit_source_body",
    "export_checkpoint",
    "promote_model",
    "walk_arxiv",
    "mine_repositories",
}

NEGATIVE_MUTATIONS = {
    "open_execution": lambda t: t.__setitem__("execution_authorized_now", True),
    "materialize_command": lambda t: t.__setitem__("command_materialized", True),
    "allow_operation": lambda t: t.__setitem__("allowed_operations_now", ["run_forward"]),
    "remove_diagnostic_gate": lambda t: t.__setitem__("post_run_diagnostic_gate_required", False),
    "open_decoder_ce": lambda t: t["required_limits"].__setitem__("decoder_ce_weight", 1.0),
    "open_runtime": lambda t: t["required_limits"].__setitem__("runtime", True),
    "open_authority": lambda t: t.__setitem__("authority", {**AUTHORITY_CLOSED, "model_execution_authorized_next": True}),
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def audit_pre_execution_ticket(ticket: dict[str, Any]) -> list[str]:
    failures = list(audit_diagnostic_ticket_fields(ticket))
    if ticket.get("ticket_status") != "TEMPLATE_ONLY_INACTIVE":
        failures.append("ticket_status_not_template_only_inactive")
    if ticket.get("execution_authorized_now") is not False:
        failures.append("execution_authorized_now_not_false")
    if ticket.get("command_materialized") is not False:
        failures.append("command_materialized_not_false")
    if ticket.get("allowed_operations_now") != []:
        failures.append("allowed_operations_now_not_empty")
    denied = set(ticket.get("denied_operations") or [])
    missing_denied = sorted(REQUIRED_DENIED_OPERATIONS - denied)
    if missing_denied:
        failures.append(f"missing_denied_operations:{missing_denied}")
    limits = ticket.get("required_limits") or {}
    for key, value in REQUIRED_LIMITS.items():
        if limits.get(key) != value:
            failures.append(f"limit_mismatch:{key}")
    if ticket.get("requires_explicit_user_authorization") is not True:
        failures.append("explicit_user_authorization_not_required")
    if ticket.get("requires_fresh_pre_execution_audit") is not True:
        failures.append("fresh_pre_execution_audit_not_required")
    if any((ticket.get("authority") or {}).values()):
        failures.append("authority_open")
    return failures


def run_negative_mutation_checks(ticket: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, mutate in NEGATIVE_MUTATIONS.items():
        candidate = copy.deepcopy(ticket)
        mutate(candidate)
        failures = audit_pre_execution_ticket(candidate)
        results[name] = {"rejected": bool(failures), "failures": failures}
    return results


def build_audit(registry: dict[str, Any], source_summary: dict[str, Any], ticket: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if source_summary.get("passed") is not True:
        failures.append("source_stage8913_not_passed")
    if any((source_summary.get("authority") or {}).values()):
        failures.append("source_stage8913_authority_open")
    ticket_failures = audit_pre_execution_ticket(ticket)
    if ticket_failures:
        failures.append(f"ticket_template_failed:{ticket_failures}")
    negative = run_negative_mutation_checks(ticket)
    for name, result in negative.items():
        if result["rejected"] is not True:
            failures.append(f"negative_mutation_not_rejected:{name}")
    metrics = registry.get("metrics") or {}
    latest = int(metrics.get("latest_stage", -1))
    if latest not in {8913, 8914, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    authority_counts = metrics.get("authority_counts") or {}
    if any(int(authority_counts.get(key, 0)) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "ticket_failures": ticket_failures,
        "negative_mutation_checks": negative,
        "negative_mutations_rejected": sum(1 for r in negative.values() if r["rejected"]),
        "required_denied_operations": sorted(REQUIRED_DENIED_OPERATIONS),
        "limits_checked": len(REQUIRED_LIMITS),
        "registry_latest_stage_observed": latest,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    source_summary = load_json(SOURCE_SUMMARY)
    ticket = load_json(SOURCE_TICKET)
    audit = build_audit(registry, source_summary, ticket)
    AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": audit["failures"],
            "ticket_failures": len(audit["ticket_failures"]),
            "negative_mutations": len(audit["negative_mutation_checks"]),
            "negative_mutations_rejected": audit["negative_mutations_rejected"],
            "limits_checked": audit["limits_checked"],
            "required_denied_operations": len(audit["required_denied_operations"]),
            "execution_authorized_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "data_mining_authorized": False,
        },
        "artifacts": {"audit": str(AUDIT.relative_to(ROOT)), "source_ticket": str(SOURCE_TICKET.relative_to(ROOT))},
        "decision": "Pre-execution audit passed for the inactive future ticket template and rejects all unsafe mutations. No execution is opened." if audit["passed"] else "Pre-execution audit failed; do not derive a live ticket.",
        "next_best_step": "Keep this audit as the mandatory final check before any future explicitly authorized one-run probe. Next no-execution work can target artifact-output path validation.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8915 Future Ticket Pre-Execution Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This no-execution audit verifies the Stage8913 inactive future ticket template and rejects unsafe mutations before any future live ticket could be derived.",
        "",
        "Rejected mutation classes: execution opened, command materialized, operation allowed, diagnostic gate removed, decoder CE opened, runtime opened, authority opened.",
        "",
        "No execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, scoring, controller merge, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8915 Future Ticket Pre-Execution Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8915 adds the final pre-execution audit for the inactive future ticket template, including negative mutation checks for opened execution, command materialization, diagnostic-gate removal, decoder/runtime loss opening, and authority opening.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
