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
STAGE = 9223
NAME = "stage9223_inactive_final_preexecution_audit_template"
PREV_SUMMARY = ROOT / "runs/summaries/stage9222_family_specific_preexecution_gap_map.json"
PREV_CARD = ROOT / "runs/local/artifacts/stage9222_family_specific_preexecution_gap_map/family_specific_preexecution_gap_map.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
CARD = OUT_DIR / "inactive_final_preexecution_audit_template.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "INACTIVE_FINAL_PREEXECUTION_AUDIT_TEMPLATE_STAGE9223.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

SUPPORTED_FAMILIES = [
    "structured_policy_probe",
    "bounded_decoder_ce_probe",
    "denoise_repair_probe",
]

REQUIRED_SECTIONS = [
    "identity_and_family_selection",
    "manifest_and_loss_mask_hashes",
    "trainer_command_surface",
    "runtime_assertion_contract",
    "telemetry_artifact_contract",
    "safe_cleanup_dry_run_contract",
    "authority_and_forbidden_paths",
    "worktree_scope",
    "decision_and_next_stage",
]

SECTION_REQUIREMENTS = {
    "identity_and_family_selection": [
        "exactly_one_family_selected_in_future_instance",
        "family_in_supported_families",
        "inactive_template_cannot_select_family",
        "no_multi_family_ticket",
    ],
    "manifest_and_loss_mask_hashes": [
        "selected_manifest_path_recorded",
        "selected_manifest_hash_recorded",
        "loss_mask_hash_recorded",
        "row_caps_recorded",
        "split_counts_recorded",
    ],
    "trainer_command_surface": [
        "mode_matches_family",
        "manifest_flag_present",
        "max_rows_flags_match_caps",
        "max_steps_recorded",
        "no_final_checkpoint_export_flag_present",
        "require_loss_mask_enforcement_audit_flag_present",
    ],
    "runtime_assertion_contract": [
        "row_count_assertions",
        "loss_mask_assertions",
        "forbidden_loss_assertions",
        "checkpoint_export_assertions",
        "authority_closed_assertions",
    ],
    "telemetry_artifact_contract": [
        "required_artifacts_declared",
        "non_empty_artifact_gate_declared",
        "row_level_failure_attribution_declared",
        "family_specific_telemetry_declared",
    ],
    "safe_cleanup_dry_run_contract": [
        "safe_cleanup_entrypoint_only",
        "dry_run_only_before_live_authority",
        "repo_root_data_root_arxiv_forbidden",
        "output_dir_marker_required",
        "cleanup_execution_false",
    ],
    "authority_and_forbidden_paths": [
        "model_execution_authority_false_in_template",
        "trainer_execution_false_in_template",
        "runtime_false_in_template",
        "arxiv_io_false_in_template",
        "source_body_emission_false_in_template",
    ],
    "worktree_scope": [
        "selected_files_only",
        "unrelated_dirty_files_ignored",
        "no_cleanup_of_untracked_files",
    ],
    "decision_and_next_stage": [
        "template_never_authorizes_same_stage_execution",
        "future_instance_may_only_recommend_next_stage_review",
        "execution_requires_separate_live_ticket_after_audit",
    ],
}

FAMILY_TELEMETRY_REQUIREMENTS = {
    "structured_policy_probe": [
        "row_field_logits.jsonl",
        "row_field_losses.jsonl",
        "row_gradient_norms.jsonl",
        "confusion_matrix.json",
        "collapse_rate_card.json",
    ],
    "bounded_decoder_ce_probe": [
        "row_token_loss.jsonl",
        "eos_length_audit.json",
        "short_output_probe.json",
        "repetition_probe.json",
        "internal_leak_probe.json",
        "module_delta_norms.json",
    ],
    "denoise_repair_probe": [
        "repair_pair_integrity.json",
        "denoise_row_loss.jsonl",
        "repair_output_quality.json",
        "internal_leak_probe.json",
        "repetition_probe.json",
        "target_resolver_readonly_proof.json",
    ],
}

TEMPLATE_METRICS_FALSE = [
    "family_selected_now",
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


def build_card() -> dict[str, Any]:
    prev = load_json(PREV_SUMMARY)
    prev_card = load_json(PREV_CARD)
    registry = load_json(REGISTRY)
    previous_families = sorted((prev_card.get("family_specific_gaps") or {}).keys())
    checks = {
        "previous_stage9222_passed": prev.get("passed") is True,
        "registry_frontier_stage9222_or_later": int((registry.get("metrics") or {}).get("latest_stage", -1)) >= 9222,
        "supported_families_match_previous_gap_map": previous_families == sorted(SUPPORTED_FAMILIES),
        "required_sections_present": len(REQUIRED_SECTIONS) == len(SECTION_REQUIREMENTS),
        "every_section_has_requirements": all(SECTION_REQUIREMENTS.get(section) for section in REQUIRED_SECTIONS),
        "family_telemetry_declared_for_all_families": sorted(FAMILY_TELEMETRY_REQUIREMENTS) == sorted(SUPPORTED_FAMILIES),
        "template_false_metric_count_sufficient": len(TEMPLATE_METRICS_FALSE) >= 20,
        "no_previous_authority_open": not any(prev.get("authority", {}).values()),
    }
    metrics = {
        "supported_families": len(SUPPORTED_FAMILIES),
        "required_sections": len(REQUIRED_SECTIONS),
        "section_requirement_total": sum(len(items) for items in SECTION_REQUIREMENTS.values()),
        "family_telemetry_artifacts": sum(len(items) for items in FAMILY_TELEMETRY_REQUIREMENTS.values()),
        "template_false_metrics": len(TEMPLATE_METRICS_FALSE),
    }
    metrics.update({key: False for key in TEMPLATE_METRICS_FALSE})
    return {
        "stage": STAGE,
        "stage_name": NAME,
        "status": "INACTIVE_FINAL_PREEXECUTION_AUDIT_TEMPLATE_NO_EXECUTION",
        "supported_families": list(SUPPORTED_FAMILIES),
        "required_sections": list(REQUIRED_SECTIONS),
        "section_requirements": SECTION_REQUIREMENTS,
        "family_telemetry_requirements": FAMILY_TELEMETRY_REQUIREMENTS,
        "template_false_metrics": list(TEMPLATE_METRICS_FALSE),
        "checks": checks,
        "metrics": metrics,
        "authority": dict(AUTHORITY_CLOSED),
        "decision": (
            "Inactive final pre-execution audit template recorded. It can be used later to build a family-specific "
            "audit after an explicit one-family request, but this template selects no family, materializes no live ticket, "
            "and authorizes no trainer/model/runtime/cleanup/mining/arxiv operation."
        ),
    }


def validate_card(card: dict[str, Any]) -> list[str]:
    failures = [key for key, value in card.get("checks", {}).items() if value is not True]
    if any((card.get("authority") or {}).values()):
        failures.append("authority_open")
    for family in SUPPORTED_FAMILIES:
        if family not in card.get("family_telemetry_requirements", {}):
            failures.append(f"missing_family_telemetry:{family}")
    for section in REQUIRED_SECTIONS:
        if section not in card.get("section_requirements", {}):
            failures.append(f"missing_section:{section}")
    for metric in TEMPLATE_METRICS_FALSE:
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
    marker = "## Stage9223 Inactive Final Preexecution Audit Template"
    text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker in text:
        return
    addition = "\n".join([
        marker,
        "",
        "Stage9223 records a reusable inactive final pre-execution audit template for the three repo-local families. It is schema/control-plane only and selects no family.",
        "The template requires manifest/loss-mask hashes, command-surface checks, runtime assertions, telemetry contracts, safe-cleanup dry-run checks, authority closure, and worktree-scope checks before any future family-specific audit can pass.",
        "No trainer, model, runtime, cleanup, mining, `/arxiv`, source/body emission, Gemma, scoring, controller merge, or promotion authority is opened.",
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
        "decision": card["decision"] if not failures else "Inactive final pre-execution audit template failed.",
        "next_best_step": "Wait for explicit one-family request before instantiating this template; otherwise continue no-execution review.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage9223 Inactive Final Preexecution Audit Template",
        "",
        f"Passed: `{summary['passed']}`",
        "",
        "Supported families:",
        *[f"- `{family}`" for family in SUPPORTED_FAMILIES],
        "",
        "Required sections:",
        *[f"- `{section}`" for section in REQUIRED_SECTIONS],
        "",
        "Family telemetry requirements:",
    ]
    for family, artifacts in FAMILY_TELEMETRY_REQUIREMENTS.items():
        lines.append(f"- `{family}`: {', '.join(f'`{artifact}`' for artifact in artifacts)}")
    lines.extend([
        "",
        "Template authority:",
        "- selects no family",
        "- materializes no live ticket",
        "- authorizes no trainer/model/runtime/cleanup/mining/arxiv operation",
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
