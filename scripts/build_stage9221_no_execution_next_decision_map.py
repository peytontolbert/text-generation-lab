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
STAGE = 9221
NAME = "stage9221_no_execution_next_decision_map"
PREV_SUMMARY = ROOT / "runs/summaries/stage9220_no_execution_trainer_readiness_gap_ledger.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "no_execution_next_decision_map.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "NO_EXECUTION_NEXT_DECISION_MAP_STAGE9221.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

FAMILY_DECISIONS = {
    "structured_policy_probe": {
        "status": "inactive_ticket_covered_not_live",
        "requires_before_any_run": [
            "explicit_user_selects_structured_policy_probe",
            "fresh_final_pre_execution_audit_for_structured_only",
            "live_ticket_materialization_from_audited_inactive_ticket",
            "telemetry_contract_recheck",
            "safe_cleanup_dry_run_recheck_without_cleanup_execution",
        ],
        "forbidden_losses": ["decoder_ce", "denoise_ce", "runtime_reward"],
    },
    "bounded_decoder_ce_probe": {
        "status": "inactive_ticket_covered_not_live",
        "requires_before_any_run": [
            "explicit_user_selects_bounded_decoder_ce_probe",
            "fresh_final_pre_execution_audit_for_bounded_decoder_only",
            "live_ticket_materialization_from_audited_inactive_ticket",
            "row_token_loss_and_generation_telemetry_contract_recheck",
            "safe_cleanup_dry_run_recheck_without_cleanup_execution",
        ],
        "forbidden_losses": ["structured_aux_unless_explicit_weighted_zero_or_audited", "denoise_ce", "runtime_reward"],
    },
    "denoise_repair_probe": {
        "status": "inactive_ticket_covered_not_live",
        "requires_before_any_run": [
            "explicit_user_selects_denoise_repair_probe",
            "fresh_final_pre_execution_audit_for_denoise_only",
            "live_ticket_materialization_from_audited_inactive_ticket",
            "target_resolver_readonly_contract_recheck",
            "safe_cleanup_dry_run_recheck_without_cleanup_execution",
        ],
        "forbidden_losses": ["decoder_ce", "structured_aux_unless_explicit_weighted_zero_or_audited", "runtime_reward"],
    },
}

DEFAULT_BRANCH_WHEN_NO_FAMILY_SELECTED = [
    "do_not_materialize_live_ticket",
    "do_not_run_final_pre_execution_audit",
    "do_not_invoke_trainer_or_model",
    "continue_docs_central_graph_or_code_review_only",
]

FORBIDDEN_ALWAYS_WITHOUT_EXPLICIT_LIVE_TICKET = [
    "trainer_execution",
    "model_forward_or_generation",
    "backward_or_optimizer",
    "checkpoint_write_or_export",
    "cleanup_execution",
    "runtime_or_verifier_runtime",
    "arxiv_access_or_mining",
    "source_body_or_patch_body_emission",
    "gemma_harness_or_scoring",
    "promotion_or_controller_merge",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    registry = load_json(REGISTRY)
    checks = {
        "previous_stage9220_passed": prev.get("passed") is True,
        "registry_latest_stage9220_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9220,
        "all_three_families_mapped": sorted(FAMILY_DECISIONS) == [
            "bounded_decoder_ce_probe",
            "denoise_repair_probe",
            "structured_policy_probe",
        ],
        "default_branch_blocks_live_ticket": "do_not_materialize_live_ticket" in DEFAULT_BRANCH_WHEN_NO_FAMILY_SELECTED,
        "forbidden_list_blocks_cleanup_and_arxiv": {"cleanup_execution", "arxiv_access_or_mining"}.issubset(set(FORBIDDEN_ALWAYS_WITHOUT_EXPLICIT_LIVE_TICKET)),
        "no_authority_open": not any(prev.get("authority", {}).values()),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "NO_EXECUTION_NEXT_DECISION_MAP",
        "family_decisions": FAMILY_DECISIONS,
        "default_branch_when_no_family_selected": DEFAULT_BRANCH_WHEN_NO_FAMILY_SELECTED,
        "forbidden_always_without_explicit_live_ticket": FORBIDDEN_ALWAYS_WITHOUT_EXPLICIT_LIVE_TICKET,
        "checks": checks,
        "metrics": {
            "family_decision_count": len(FAMILY_DECISIONS),
            "default_branch_blocks": len(DEFAULT_BRANCH_WHEN_NO_FAMILY_SELECTED),
            "forbidden_without_live_ticket": len(FORBIDDEN_ALWAYS_WITHOUT_EXPLICIT_LIVE_TICKET),
            "explicit_one_family_request_present": False,
            "live_ticket_materialized_now": False,
            "final_pre_execution_audit_authorized_now": False,
            "same_stage_execution_authorized": False,
            "next_stage_execution_authorized": False,
            "trainer_executed_now": False,
            "model_forward_attempted": False,
            "backward_attempted": False,
            "optimizer_created": False,
            "checkpoint_written_now": False,
            "cleanup_authorized_now": False,
            "runtime_authorized_flag": False,
            "runtime_verifier_execution_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "arxiv_read_authorized_for_compiler": False,
            "arxiv_write_authorized": False,
            "data_mining_authorized": False,
        },
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "No-execution next-decision map recorded. Without an explicit one-family request, the only valid branch "
            "is documentation/central-graph review; live tickets, final pre-execution audit, trainer/model/runtime, "
            "cleanup, mining, and /arxiv access remain blocked."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for family, spec in card.get("family_decisions", {}).items():
        if not spec.get("requires_before_any_run"):
            failures.append(f"missing_requirements:{family}")
        if spec.get("status") != "inactive_ticket_covered_not_live":
            failures.append(f"family_status_not_inactive:{family}")
    for key in [
        "explicit_one_family_request_present",
        "live_ticket_materialized_now",
        "final_pre_execution_audit_authorized_now",
        "same_stage_execution_authorized",
        "next_stage_execution_authorized",
        "trainer_executed_now",
        "model_forward_attempted",
        "backward_attempted",
        "optimizer_created",
        "checkpoint_written_now",
        "cleanup_authorized_now",
        "runtime_authorized_flag",
        "runtime_verifier_execution_authorized",
        "decoder_ce_authorized",
        "denoise_ce_authorized",
        "arxiv_read_authorized_for_compiler",
        "arxiv_write_authorized",
        "data_mining_authorized",
    ]:
        if card["metrics"].get(key) is not False:
            failures.append(key)
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
    marker = "## Stage9221 No-Execution Next Decision Map"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9221 maps the only valid branches after Stage9220. If no family is explicitly selected, no live ticket, final pre-execution audit, trainer invocation, model forward/backward, cleanup, runtime, mining, or /arxiv access may occur.",
        "Each family remains inactive-ticket-covered but not live: structured-policy, bounded-decoder CE, and denoise-repair.",
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
        "decision": card["decision"] if not failures else "No-execution next decision map failed.",
        "next_best_step": "If training is desired later, explicitly select one family; otherwise continue no-execution central graph review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9221 No-Execution Next Decision Map",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Default branch when no family is selected:",
        *[f"- `{item}`" for item in DEFAULT_BRANCH_WHEN_NO_FAMILY_SELECTED],
        "",
        "Families:",
    ]
    for family, spec in FAMILY_DECISIONS.items():
        lines.extend([f"- `{family}`: `{spec['status']}`"])
    lines.extend([
        "",
        "Forbidden without explicit live ticket:",
        *[f"- `{item}`" for item in FORBIDDEN_ALWAYS_WITHOUT_EXPLICIT_LIVE_TICKET],
        "",
        f"Next: {summary['next_best_step']}",
    ])
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if not failures:
        append_spine(summary)
        update_registry(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["passed"] else 1)


if __name__ == "__main__":
    main()
