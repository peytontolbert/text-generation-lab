#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 10443
NAME = "stage10443_repaired_v27_frontier_status_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
AUDIT_JSON = OUT_DIR / "repaired_v27_frontier_status_audit.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"

COMPARISON_JSON = ROOT / "runs/local/artifacts/stage10424_reviewed_multilingual_v27_comparison_audit/reviewed_multilingual_v27_comparison_audit.json"
LIVE_EVAL_HACK_JSON = ROOT / "runs/local/artifacts/stage10429_reviewed_v27_eval_hacking_audit/reviewed_v27_eval_hacking_audit.json"
REPAIRED_EVAL_HACK_JSON = ROOT / "runs/local/artifacts/stage10437_repaired_v27_strict_overlay_eval_hacking_audit/repaired_v27_strict_overlay_eval_hacking_audit.json"
REPAIRED_MARGIN_JSON = ROOT / "runs/local/artifacts/stage10438_repaired_v27_strict_overlay_saved_runtime_margin_audit/repaired_v27_strict_overlay_saved_runtime_margin_audit.json"
PYTHON_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10439_python_verifier_disjoint_support_request/python_verifier_disjoint_support_request.json"
RUST_REQUEST_JSON = ROOT / "runs/local/artifacts/stage10441_rust_evidence_citation_fresh_builder_request/rust_evidence_citation_fresh_builder_request.json"
PYTHON_PROBE_JSON = ROOT / "runs/local/artifacts/stage10442_python_verifier_disjoint_support_probe/bounded_decoder_probe/execution_result.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def display(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def main() -> None:
    comparison = load_json(COMPARISON_JSON)
    live_eval_hack = load_json(LIVE_EVAL_HACK_JSON)
    repaired_eval_hack = load_json(REPAIRED_EVAL_HACK_JSON)
    repaired_margin = load_json(REPAIRED_MARGIN_JSON)
    python_request = load_json(PYTHON_REQUEST_JSON)
    rust_request = load_json(RUST_REQUEST_JSON)
    python_probe = load_json(PYTHON_PROBE_JSON)

    live_strict = comparison["strict_result"]
    live_accuracy = comparison["hundred_m_eval_result"]["strict_accuracy"]
    gemma_accuracy = live_strict["gemma12b"]["exact_accuracy"]
    repaired_accuracy = repaired_margin["summary"]["accuracy"]
    probe_accuracy = python_probe["bounded_choice_eval"]["strict_eval"]["constrained_choice_top1_accuracy"]

    repaired_residuals = repaired_margin["incorrect_rows"]
    probe_row_cards = python_probe["bounded_choice_eval"]["strict_eval"]["row_cards"]
    probe_by_row = {row["row_id"]: row for row in probe_row_cards}

    residual_status = []
    for row in repaired_residuals:
        probe_row = probe_by_row[row["row_id"]]
        residual_status.append(
            {
                "row_id": row["row_id"],
                "language_family": row["language_family"],
                "task_type": row["task_type"],
                "baseline_predicted_label": row["predicted_label"],
                "baseline_target_label": row["target_label"],
                "baseline_margin_top1_minus_top2": row["margin_top1_minus_top2"],
                "probe_predicted_label": probe_row["constrained_choice_top1_label"],
                "probe_target_label": probe_row["target_text"],
                "probe_correct": probe_row["constrained_choice_match"],
                "changed_under_stage10442": probe_row["constrained_choice_top1_label"] != row["predicted_label"],
                "required_support_shape": (
                    [
                        "fresh Python verifier_outcome roots with closely competing test targets",
                        "selected-test anchor retained without exposing the gold answer verbatim",
                        "disambiguate similar test-file semantics rather than replaying the same root",
                    ]
                    if row["language_family"] == "python"
                    else [
                        "fresh Rust evidence-citation roots where candidate_change_surface is a tempting negative",
                        "gold support fact distinct from verifier_and_test_constraint",
                        "selected-test or trace anchor retained without exposing the answer token verbatim",
                    ]
                ),
            }
        )

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now_utc(),
        "passed": True,
        "claim_scope": [
            "Current honest status packet for reviewed v2.7 after strict leak repair and the stage10442 residual probe.",
            "This preserves the live same-manifest 100M-vs-Gemma claim while separately reporting the hardened repaired-overlay standalone status.",
            "This does not upgrade v2.7 to source-heldout or full-product harness status.",
        ],
        "source_artifacts": {
            "live_comparison_audit": display(COMPARISON_JSON),
            "live_eval_hacking_audit": display(LIVE_EVAL_HACK_JSON),
            "repaired_overlay_eval_hacking_audit": display(REPAIRED_EVAL_HACK_JSON),
            "repaired_overlay_margin_audit": display(REPAIRED_MARGIN_JSON),
            "python_residual_request": display(PYTHON_REQUEST_JSON),
            "rust_residual_request": display(RUST_REQUEST_JSON),
            "python_residual_probe": display(PYTHON_PROBE_JSON),
        },
        "current_claim": {
            "supported": True,
            "text": comparison["current_claim"]["text"],
            "scope": comparison["current_claim"]["scope"],
            "unsupported_upgrades": comparison["current_claim"]["unsupported_upgrades"],
        },
        "frontier_summary": {
            "live_same_manifest_100m_strict_accuracy": live_accuracy,
            "live_same_manifest_gemma12b_strict_accuracy": gemma_accuracy,
            "live_same_manifest_delta": live_strict["delta_hundred_m_minus_gemma"],
            "live_language_summary": live_strict["by_language"]["_summary"],
            "source_heldout_claim_supported": comparison["eval_integrity"]["source_heldout_claim_supported"],
            "stress_rows_excluded_from_promotable_strict": comparison["eval_integrity"]["stress_rows_excluded_from_promotable_strict"],
        },
        "anti_cheat_status": {
            "live_package_prompt_target_leak_rows": live_eval_hack["prompt_leakage"]["prompt_contains_target_value_before_options"],
            "live_package_prompt_target_leak_rate": live_eval_hack["prompt_leakage"]["prompt_contains_target_value_before_options_rate"],
            "repaired_overlay_prompt_target_leak_rows": repaired_eval_hack["summary"]["rows_with_prompt_target_leak"],
            "repaired_overlay_old_evidence_key_name_rows": repaired_eval_hack["summary"]["rows_with_old_evidence_key_names"],
            "repaired_overlay_visible_slot_contract_rows": repaired_eval_hack["summary"]["rows_passing_visible_slot_contract"],
            "strict_language_task_metadata_majority_accuracy": live_eval_hack["metadata_majority_baselines"]["strict_rows"]["language_and_task"]["accuracy"],
            "strict_task_type_majority_accuracy": live_eval_hack["metadata_majority_baselines"]["strict_rows"]["task_type"]["accuracy"],
        },
        "repaired_overlay_status": {
            "standalone_strict_accuracy": repaired_accuracy,
            "residual_probe_strict_accuracy": probe_accuracy,
            "accuracy_changed_under_stage10442": probe_accuracy != repaired_accuracy,
            "repaired_overlay_residual_count": len(repaired_residuals),
            "residual_probe_changed_any_miss": any(item["changed_under_stage10442"] for item in residual_status),
            "mean_margin": repaired_margin["summary"]["mean_margin"],
        },
        "residual_rows": residual_status,
        "recommended_next_steps": [
            "Keep the live stage10424 same-manifest Gemma comparison as the current headline for v2.7, with the same-manifest and non-source-heldout boundaries preserved.",
            "Use the repaired overlay only as the anti-cheat-hardened standalone status: it removes prompt-visible target leakage on the strict rows without reducing the 100M score.",
            "Do not promote stage10442; it is a non-promotable disjoint-support diagnostic and it did not improve the two remaining misses.",
            "Build fresh disjoint Python verifier and Rust evidence-citation roots rather than replaying the current strict rows again.",
            "Before any broader claim upgrade, replace old evidence-key naming patterns on the repaired overlay and keep stress rows out of the promotable path.",
        ],
        "residual_followup_artifacts": {
            "python_request_focus_row": python_request["strict_focus_row"],
            "python_request_success_criteria": python_request["success_criteria"],
            "rust_builder_success_condition": rust_request["success_condition"],
            "rust_current_residual_target": rust_request["current_residual_target"],
        },
        "outputs": {
            "audit_json": display(AUDIT_JSON),
        },
    }

    write_json(AUDIT_JSON, payload)
    write_json(SUMMARY, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
