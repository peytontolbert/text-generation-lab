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
STAGE = 9232
NAME = "stage9232_explicit_request_intake_checklist"
PREV_SUMMARY = ROOT / "runs/summaries/stage9231_frontier_after_audit_design_schema_audit.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "explicit_request_intake_checklist.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EXPLICIT_REQUEST_INTAKE_CHECKLIST_STAGE9232.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

SUPPORTED_FAMILIES = ["structured_policy_probe", "bounded_decoder_ce_probe", "denoise_repair_probe"]

REQUIRED_USER_INTENT_SIGNALS = [
    "names_exactly_one_supported_family",
    "says_design_family_specific_final_preexecution_audit_only",
    "keeps_same_stage_execution_false",
    "keeps_trainer_model_cleanup_runtime_arxiv_false",
    "accepts_no_live_ticket_materialization",
]

AMBIGUOUS_OR_UNSAFE_PHRASES = {
    "continue": "not_a_family_selection",
    "run it": "execution_requested",
    "start training": "trainer_invocation_requested",
    "use all families": "multiple_families_requested",
    "clean up": "cleanup_requested",
    "read arxiv": "arxiv_access_requested",
    "execute runtime": "runtime_requested",
    "write checkpoint": "checkpoint_requested",
}

INTAKE_DECISIONS = {
    "valid_design_request": "may_build_family_specific_final_preexecution_audit_design_only",
    "ambiguous_request": "continue_no_execution_review_or_ask_for_precise_family",
    "unsafe_request": "reject_execution_and_keep_authority_closed",
}

CLOSED_METRICS = [
    "valid_request_present",
    "intake_request_processed_now",
    "family_selected_now",
    "family_specific_final_audit_design_instantiated_now",
    "live_ticket_materialized_now",
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


def classify_request_text(text: str) -> dict[str, Any]:
    lowered = text.lower()
    matched_unsafe = [phrase for phrase in AMBIGUOUS_OR_UNSAFE_PHRASES if phrase in lowered and phrase != "continue"]
    family_hits = [family for family in SUPPORTED_FAMILIES if family in text]
    design_only = "design_family_specific_final_preexecution_audit_only" in text
    closed_terms = all(term in lowered for term in ["trainer=false", "model=false", "cleanup=false", "arxiv=false", "runtime=false"])
    if matched_unsafe:
        return {"decision": "unsafe_request", "family_hits": family_hits, "reasons": [AMBIGUOUS_OR_UNSAFE_PHRASES[p] for p in matched_unsafe]}
    if len(family_hits) == 1 and design_only and closed_terms:
        return {"decision": "valid_design_request", "family_hits": family_hits, "reasons": []}
    return {"decision": "ambiguous_request", "family_hits": family_hits, "reasons": ["required_intent_signals_missing"]}


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    registry = load_json(REGISTRY)
    examples = {
        "casual_continue": classify_request_text("please continue"),
        "valid_structured_design": classify_request_text("requested_family=structured_policy_probe request_scope=design_family_specific_final_preexecution_audit_only trainer=false model=false cleanup=false arxiv=false runtime=false"),
        "unsafe_run": classify_request_text("run it for bounded_decoder_ce_probe"),
        "unsafe_cleanup": classify_request_text("clean up and start training"),
    }
    checks = {
        "previous_stage9231_passed": prev.get("passed") is True,
        "registry_frontier_stage9231_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9231,
        "supported_families_three": len(SUPPORTED_FAMILIES) == 3,
        "required_signals_recorded": len(REQUIRED_USER_INTENT_SIGNALS) >= 5,
        "continue_is_not_valid_request": examples["casual_continue"]["decision"] == "ambiguous_request",
        "valid_example_is_design_only": examples["valid_structured_design"]["decision"] == "valid_design_request",
        "unsafe_examples_rejected": examples["unsafe_run"]["decision"] == "unsafe_request" and examples["unsafe_cleanup"]["decision"] == "unsafe_request",
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "supported_families": len(SUPPORTED_FAMILIES),
        "required_user_intent_signals": len(REQUIRED_USER_INTENT_SIGNALS),
        "ambiguous_or_unsafe_phrases": len(AMBIGUOUS_OR_UNSAFE_PHRASES),
        "intake_examples": len(examples),
    }
    metrics.update({key: False for key in CLOSED_METRICS})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "EXPLICIT_REQUEST_INTAKE_CHECKLIST_NO_EXECUTION",
        "supported_families": SUPPORTED_FAMILIES,
        "required_user_intent_signals": REQUIRED_USER_INTENT_SIGNALS,
        "ambiguous_or_unsafe_phrases": AMBIGUOUS_OR_UNSAFE_PHRASES,
        "intake_decisions": INTAKE_DECISIONS,
        "examples": examples,
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": "Explicit request intake checklist recorded. Casual continuation is not a valid family selection; unsafe execution, cleanup, runtime, checkpoint, training, and /arxiv phrasing remains rejected.",
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    if card.get("examples", {}).get("casual_continue", {}).get("decision") == "valid_design_request":
        failures.append("casual_continue_treated_as_valid")
    for metric in CLOSED_METRICS:
        if card.get("metrics", {}).get(metric) is not False:
            failures.append(metric)
    return failures


def update_registry(summary: dict[str, Any]) -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    rows = [row for row in registry.get("rows", []) if row.get("stage") != STAGE and row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": summary["passed"], "path": str(SUMMARY), "authority": dict(AUTHORITY_CLOSED), "next_best_step": summary["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = summary["passed"]
    registry["metrics"] = {**(registry.get("metrics") or {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": summary["next_best_step"], "max_stage": max(STAGE, int((registry.get("metrics") or {}).get("max_stage", 0))), "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_spine(summary: dict[str, Any]) -> None:
    marker = "## Stage9232 Explicit Request Intake Checklist"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([marker, "", "Stage9232 records an intake checklist before Stage9225 request validation. Casual continuation is ambiguous, not a family selection; unsafe run/training/cleanup/runtime/arxiv/checkpoint language is rejected.", "No request is processed and no authority is opened.", "", f"Next: {summary['next_best_step']}", ""])
    SPINE.write_text(text.rstrip() + "\n\n" + addition, encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    card = build_card()
    failures = validate_card(card)
    CARD.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": dict(AUTHORITY_CLOSED), "metrics": {**dict(AUTHORITY_CLOSED), "failures": failures, **card["metrics"]}, "artifacts": {"card": str(CARD.relative_to(ROOT)), "doc": str(DOC.relative_to(ROOT))}, "decision": card["decision"] if not failures else "Explicit request intake checklist failed.", "next_best_step": "Wait for a valid explicit one-family request, or continue no-execution central graph review.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage9232 Explicit Request Intake Checklist", "", f"Passed: `{summary['passed']}`", "", "Required user intent signals:", *[f"- `{item}`" for item in REQUIRED_USER_INTENT_SIGNALS], "", "Ambiguous or unsafe phrase handling:", *[f"- `{phrase}` -> `{reason}`" for phrase, reason in AMBIGUOUS_OR_UNSAFE_PHRASES.items()], "", "Example decisions:", *[f"- `{name}` -> `{result['decision']}`" for name, result in card["examples"].items()], "", f"Next: {summary['next_best_step']}"]) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
