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
STAGE = 9222
NAME = "stage9222_family_specific_preexecution_gap_map"
PREV_SUMMARY = ROOT / "runs/summaries/stage9221_no_execution_next_decision_map.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9221_no_execution_next_decision_map/no_execution_next_decision_map.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "family_specific_preexecution_gap_map.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FAMILY_SPECIFIC_PREEXECUTION_GAP_MAP_STAGE9222.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

COMMON_PREEXECUTION_GAPS = [
    "explicit_one_family_request",
    "fresh_family_specific_final_preexecution_audit",
    "live_ticket_materialization_from_inactive_ticket",
    "selected_manifest_hash_recheck",
    "selected_loss_mask_hash_recheck",
    "trainer_command_surface_recheck",
    "runtime_assertion_contract_recheck",
    "telemetry_artifact_contract_recheck",
    "safe_cleanup_dry_run_recheck_without_cleanup_execution",
    "clean_nonconflicting_worktree_scope_for_selected_files",
]

FAMILY_GAPS = {
    "structured_policy_probe": [
        "structured_aux_only_loss_mask_recheck",
        "decoder_ce_weight_zero_recheck",
        "denoise_weight_zero_recheck",
        "row_field_logits_losses_gradients_required",
        "collapse_and_confusion_matrix_required",
    ],
    "bounded_decoder_ce_probe": [
        "bounded_decoder_only_loss_mask_recheck",
        "target_token_cap_recheck",
        "row_token_loss_real_per_position_required",
        "eos_length_short_junk_repetition_leak_required",
        "decoder_module_delta_guard_required",
    ],
    "denoise_repair_probe": [
        "denoise_only_loss_mask_recheck",
        "target_resolver_readonly_recheck",
        "corrupted_to_clean_pair_integrity_recheck",
        "repair_output_leak_short_repetition_required",
        "no_runtime_verifier_execution_recheck",
    ],
}

GLOBAL_FORBIDDEN = [
    "training_without_family_selection",
    "multi_family_live_ticket",
    "trainer_execution_before_final_audit",
    "checkpoint_write_or_export_before_live_authority",
    "cleanup_execution_before_live_authority",
    "arxiv_read_write_mining_before_source_ticket",
    "runtime_or_verifier_runtime_before_runtime_ticket",
    "body_source_patch_emission_before_authority",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    previous_families = sorted((prev_card.get("family_decisions") or {}).keys())
    checks = {
        "previous_stage9221_passed": prev.get("passed") is True,
        "registry_frontier_stage9221_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9221,
        "all_previous_families_have_gap_maps": previous_families == sorted(FAMILY_GAPS),
        "common_gap_count_sufficient": len(COMMON_PREEXECUTION_GAPS) >= 10,
        "each_family_has_five_specific_gaps": all(len(gaps) >= 5 for gaps in FAMILY_GAPS.values()),
        "global_forbidden_blocks_cleanup_arxiv_runtime": {"cleanup_execution_before_live_authority", "arxiv_read_write_mining_before_source_ticket", "runtime_or_verifier_runtime_before_runtime_ticket"}.issubset(set(GLOBAL_FORBIDDEN)),
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "FAMILY_SPECIFIC_PREEXECUTION_GAP_MAP_NO_EXECUTION",
        "common_preexecution_gaps": list(COMMON_PREEXECUTION_GAPS),
        "family_specific_gaps": FAMILY_GAPS,
        "global_forbidden": list(GLOBAL_FORBIDDEN),
        "checks": checks,
        "metrics": {
            "family_gap_maps": len(FAMILY_GAPS),
            "common_preexecution_gaps": len(COMMON_PREEXECUTION_GAPS),
            "family_specific_gap_total": sum(len(gaps) for gaps in FAMILY_GAPS.values()),
            "global_forbidden_items": len(GLOBAL_FORBIDDEN),
            "explicit_one_family_request_present": False,
            "family_selected_now": False,
            "final_pre_execution_audit_authorized_now": False,
            "live_ticket_materialized_now": False,
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
            "Family-specific pre-execution gaps are now explicit. This is a no-execution map only: selecting a family, "
            "materializing a live ticket, final pre-execution audit, trainer/model invocation, cleanup, runtime, mining, "
            "and /arxiv access all remain closed."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for family in ["structured_policy_probe", "bounded_decoder_ce_probe", "denoise_repair_probe"]:
        if family not in card.get("family_specific_gaps", {}):
            failures.append(f"missing_family_gap_map:{family}")
    for required in ["explicit_one_family_request", "fresh_family_specific_final_preexecution_audit", "safe_cleanup_dry_run_recheck_without_cleanup_execution"]:
        if required not in card.get("common_preexecution_gaps", []):
            failures.append(f"missing_common_gap:{required}")
    for key in [
        "explicit_one_family_request_present",
        "family_selected_now",
        "final_pre_execution_audit_authorized_now",
        "live_ticket_materialized_now",
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
    marker = "## Stage9222 Family-Specific Preexecution Gap Map"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9222 makes the remaining pre-execution gaps family-specific: structured-policy, bounded-decoder CE, and denoise-repair each require selected-manifest/loss-mask, command, runtime assertion, telemetry, and safe-cleanup dry-run rechecks before any future live ticket can run.",
        "This stage does not select a family and opens no execution authority.",
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
        "decision": card["decision"] if not failures else "Family-specific pre-execution gap map failed.",
        "next_best_step": "Either stop, or if the user explicitly chooses one family, build that family-specific final pre-execution audit design only.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9222 Family-Specific Preexecution Gap Map",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Common gaps before any trainer invocation:",
        *[f"- `{gap}`" for gap in COMMON_PREEXECUTION_GAPS],
        "",
        "Family-specific gaps:",
    ]
    for family, gaps in FAMILY_GAPS.items():
        lines.append(f"- `{family}`: {', '.join(f'`{gap}`' for gap in gaps)}")
    lines.extend([
        "",
        "Global forbidden without explicit live ticket:",
        *[f"- `{item}`" for item in GLOBAL_FORBIDDEN],
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
