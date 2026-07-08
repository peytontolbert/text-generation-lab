#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from diagnostic_ticket_contract import AUTHORITY_CLOSED
except ModuleNotFoundError:  # pragma: no cover
    from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STAGE = 9225
NAME = "stage9225_explicit_one_family_request_schema"
PREV_SUMMARY = ROOT / "runs/summaries/stage9224_current_frontier_handoff_after_template.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9224_current_frontier_handoff_after_template/current_frontier_handoff_after_template.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "explicit_one_family_request_schema.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPLICIT_ONE_FAMILY_REQUEST_SCHEMA_STAGE9225.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

SUPPORTED_FAMILIES = [
    "structured_policy_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

REQUIRED_REQUEST_FIELDS = [
    "requested_family",
    "request_scope",
    "allowed_next_artifact",
    "same_stage_execution_allowed",
    "trainer_invocation_allowed",
    "model_forward_allowed",
    "cleanup_allowed",
    "arxiv_access_allowed",
    "runtime_allowed",
    "checkpoint_export_allowed",
]

VALID_REQUEST_VALUES = {
    "request_scope": "design_family_specific_final_preexecution_audit_only",
    "allowed_next_artifact": "family_specific_final_preexecution_audit_design",
    "same_stage_execution_allowed": False,
    "trainer_invocation_allowed": False,
    "model_forward_allowed": False,
    "cleanup_allowed": False,
    "arxiv_access_allowed": False,
    "runtime_allowed": False,
    "checkpoint_export_allowed": False,
}

REQUEST_REJECTION_REASONS = [
    "missing_requested_family",
    "unsupported_requested_family",
    "multiple_families_requested",
    "same_stage_execution_requested",
    "trainer_invocation_requested",
    "model_forward_or_generation_requested",
    "cleanup_requested",
    "arxiv_access_requested",
    "runtime_requested",
    "checkpoint_export_requested",
    "scope_not_design_only",
]

TEMPLATE_EXAMPLE = {
    "requested_family": "structured_policy_probe",
    "request_scope": "design_family_specific_final_preexecution_audit_only",
    "allowed_next_artifact": "family_specific_final_preexecution_audit_design",
    "same_stage_execution_allowed": False,
    "trainer_invocation_allowed": False,
    "model_forward_allowed": False,
    "cleanup_allowed": False,
    "arxiv_access_allowed": False,
    "runtime_allowed": False,
    "checkpoint_export_allowed": False,
}

CLOSED_METRICS = [
    "family_selected_now",
    "live_ticket_materialized_now",
    "family_specific_final_audit_instantiated_now",
    "same_stage_execution_authorized",
    "next_stage_execution_authorized",
    "trainer_executed_now",
    "model_forward_attempted",
    "generation_attempted",
    "backward_attempted",
    "optimizer_created",
    "checkpoint_written_now",
    "checkpoint_export_authorized",
    "cleanup_authorized_now",
    "cleanup_executed_now",
    "runtime_authorized_flag",
    "runtime_verifier_execution_authorized",
    "decoder_ce_authorized",
    "denoise_ce_authorized",
    "arxiv_read_authorized_for_compiler",
    "arxiv_write_authorized",
    "data_mining_authorized",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def validate_request(request: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if "requested_family" not in request:
        failures.append("missing_requested_family")
    family = request.get("requested_family")
    if isinstance(family, list):
        failures.append("multiple_families_requested")
    elif family is not None and family not in SUPPORTED_FAMILIES:
        failures.append("unsupported_requested_family")
    for key, expected in VALID_REQUEST_VALUES.items():
        if request.get(key) != expected:
            if key == "request_scope":
                failures.append("scope_not_design_only")
            elif key == "same_stage_execution_allowed":
                failures.append("same_stage_execution_requested")
            elif key == "trainer_invocation_allowed":
                failures.append("trainer_invocation_requested")
            elif key == "model_forward_allowed":
                failures.append("model_forward_or_generation_requested")
            elif key == "cleanup_allowed":
                failures.append("cleanup_requested")
            elif key == "arxiv_access_allowed":
                failures.append("arxiv_access_requested")
            elif key == "runtime_allowed":
                failures.append("runtime_requested")
            elif key == "checkpoint_export_allowed":
                failures.append("checkpoint_export_requested")
            else:
                failures.append(f"invalid_{key}")
    return failures


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    previous_valid_branches = set(prev_card.get("only_valid_next_branches") or [])
    checks = {
        "previous_stage9224_passed": prev.get("passed") is True,
        "registry_frontier_stage9224_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9224,
        "supported_families_three": len(SUPPORTED_FAMILIES) == 3,
        "required_fields_recorded": len(REQUIRED_REQUEST_FIELDS) == 10,
        "template_example_valid": validate_request(TEMPLATE_EXAMPLE) == [],
        "rejection_reasons_cover_execution_cleanup_arxiv": {"trainer_invocation_requested", "cleanup_requested", "arxiv_access_requested"}.issubset(set(REQUEST_REJECTION_REASONS)),
        "previous_valid_branch_mentions_one_family": "if_user_selects_exactly_one_family_build_family_specific_final_preexecution_audit_design_only" in previous_valid_branches,
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "supported_families": len(SUPPORTED_FAMILIES),
        "required_request_fields": len(REQUIRED_REQUEST_FIELDS),
        "request_rejection_reasons": len(REQUEST_REJECTION_REASONS),
        "template_example_failures": len(validate_request(TEMPLATE_EXAMPLE)),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "EXPLICIT_ONE_FAMILY_REQUEST_SCHEMA_NO_EXECUTION",
        "supported_families": list(SUPPORTED_FAMILIES),
        "required_request_fields": list(REQUIRED_REQUEST_FIELDS),
        "valid_request_values": dict(VALID_REQUEST_VALUES),
        "request_rejection_reasons": list(REQUEST_REJECTION_REASONS),
        "template_example": dict(TEMPLATE_EXAMPLE),
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Explicit one-family request schema recorded. This stage does not select a family or instantiate a final "
            "audit; it defines the only acceptable future request shape and rejects any request that asks for trainer, "
            "model, cleanup, runtime, checkpoint export, mining, or /arxiv access."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if validate_request(card.get("template_example") or {}):
        failures.append("template_example_invalid")
    for family in SUPPORTED_FAMILIES:
        if family not in card.get("supported_families", []):
            failures.append(f"missing_supported_family:{family}")
    for metric in CLOSED_METRICS:
        if card.get("metrics", {}).get(metric) is not False:
            failures.append(metric)
    return failures


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": summary["passed"],
        "path": str(SUMMARY),
        "authority": dict(AUTHORITY_CLOSED),
        "next_best_step": summary["next_best_step"],
    })
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


def append_spine(summary: dict[str, Any]) -> None:
    marker = "## Stage9225 Explicit One-Family Request Schema"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9225 defines what an explicit one-family request must look like before any family-specific final pre-execution audit design can be instantiated.",
        "The schema only permits a design-only request for one of structured-policy, bounded-decoder CE, or denoise-repair. It rejects trainer/model execution, cleanup, runtime, checkpoint export, mining, and `/arxiv` access.",
        "No family is selected by this stage and no authority is opened.",
        "",
        f"Next: {summary['next_best_step']}",
        "",
    ])
    SPINE.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = build_card()
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]},
        "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))},
        "decision": card["decision"] if not failures else "Explicit one-family request schema failed.",
        "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage9225 Explicit One-Family Request Schema",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Supported families:",
        *[f"- `{family}`" for family in SUPPORTED_FAMILIES],
        "",
        "Required request fields:",
        *[f"- `{field}`" for field in REQUIRED_REQUEST_FIELDS],
        "",
        "Rejected request classes:",
        *[f"- `{reason}`" for reason in REQUEST_REJECTION_REASONS],
        "",
        "Template example:",
        "```json",
        json.dumps(TEMPLATE_EXAMPLE, indent=2, sort_keys=True),
        "```",
        "",
        f"Next: {summary['next_best_step']}",
    ]) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
