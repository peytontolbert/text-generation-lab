#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8895
NAME = "stage8895_stage8890_live_authorization_checklist"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STAGE8890_LIVE_AUTHORIZATION_CHECKLIST_STAGE8895.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

SOURCE_SUMMARIES = {
    "preflight_plan_review": "runs/summaries/stage8882_tiny_structured_probe_execution_authorization_review.json",
    "inactive_ticket_design": "runs/summaries/stage8886_stage8890_inactive_execution_ticket_design.json",
    "inactive_ticket_gate": "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
    "control_plane_regression": "runs/summaries/stage8891_no_execution_control_plane_regression_audit.json",
    "decision_matrix": "runs/summaries/stage8892_next_steps_decision_matrix_after_control_plane_regression.json",
    "telemetry_gate_matrix": "runs/summaries/stage8893_no_execution_telemetry_gate_matrix.json",
    "frontier_collision_guard": "runs/summaries/stage8894_registry_frontier_collision_guard.json",
}

REQUIRED_STAGE8890_LIMITS = {
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

REQUIRED_AFTER_RUN_ARTIFACTS = [
    "loss_by_step.jsonl",
    "eval_loss_by_checkpoint.jsonl",
    "row_field_logits.jsonl",
    "row_field_losses.jsonl",
    "row_gradient_norms.jsonl",
    "activation_summary.jsonl",
    "feature_ablation_attribution.jsonl",
    "activation_patch_recovery.jsonl",
    "row_dynamics_history.jsonl",
    "module_delta_norms.json",
    "field_exact_by_cell.json",
    "field_label_vocabs.json",
    "structured_confusion_matrix.json",
    "failure_bucket_card.json",
    "cleanup_proof.json",
]

FORBIDDEN_AT_LIVE_STAGE = [
    "decoder_ce_training",
    "denoise_ce_training",
    "runtime_execution",
    "source_body_emission",
    "gemma_execution",
    "harness_scoring",
    "checkpoint_export",
    "promotion",
    "arxiv_walk",
    "commit_inventory_read",
    "data_mining",
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_checklist(registry: dict[str, Any], source_cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failures: list[str] = []
    source_status = {}
    for key, rel in SOURCE_SUMMARIES.items():
        card = source_cards.get(key) or {}
        passed = card.get("passed") is True
        authority_closed = not any((card.get("authority") or {}).values())
        source_status[key] = {"path": rel, "passed": passed, "authority_closed": authority_closed}
        if not passed:
            failures.append(f"source_not_passed:{key}")
        if not authority_closed:
            failures.append(f"source_authority_open:{key}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    latest = (registry.get("metrics") or {}).get("latest_stage")
    if latest not in {8894, STAGE}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any(int(row.get("stage", -1)) == 8890 for row in registry.get("rows", [])):
        failures.append("stage8890_already_materialized")
    checklist = {
        "checklist_id": "stage8890_live_authorization_checklist_v1",
        "status": "NO_LIVE_AUTHORITY_CHECKLIST_ONLY",
        "stage8890_reserved": True,
        "live_authorization_created_now": False,
        "requires_explicit_user_phrase": "authorize the one-run Stage8890 structured probe",
        "required_before_ticket": [
            "clean_git_worktree_or_explicit_dirty_scope",
            "registry_frontier_collision_guard_passed",
            "inactive_ticket_gate_passed",
            "telemetry_gate_matrix_passed",
            "native_probe_preflight_plan_unchanged_or_refreshed",
            "safe_cleanup_tests_passed",
            "artifact_contract_tests_passed",
            "no_arxiv_or_commit_inventory_side_effects",
        ],
        "required_stage8890_limits": dict(REQUIRED_STAGE8890_LIMITS),
        "required_after_run_artifacts": list(REQUIRED_AFTER_RUN_ARTIFACTS),
        "forbidden_at_live_stage": list(FORBIDDEN_AT_LIVE_STAGE),
        "source_status": source_status,
    }
    return {"checklist": checklist, "failures": failures}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    source_cards = {key: load(ROOT / rel) for key, rel in SOURCE_SUMMARIES.items()}
    built = build_checklist(registry, source_cards)
    checklist = built["checklist"]
    failures = built["failures"]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": failures,
            "source_cards_checked": len(SOURCE_SUMMARIES),
            "required_after_run_artifacts": len(REQUIRED_AFTER_RUN_ARTIFACTS),
            "forbidden_at_live_stage": len(FORBIDDEN_AT_LIVE_STAGE),
            "live_authorization_created_now": False,
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "arxiv_walk_authorized": False,
            "commit_inventory_read_authorized": False,
        },
        "checklist": checklist,
        "decision": "Stage8890 live-authorization checklist recorded. It creates no live ticket and opens no authority." if not failures else "Stage8890 live-authorization checklist failed prerequisites.",
        "next_best_step": "Use this checklist only if the user explicitly authorizes the one-run Stage8890 structured probe. Otherwise continue no-execution hardening or stop.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "stage8890_live_authorization_checklist.json").write_text(json.dumps(checklist, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8895 Stage8890 Live Authorization Checklist",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "This is a checklist only. It does not issue a live ticket and does not run the Stage8890 probe.",
        "",
        "A future live ticket must preserve: structured-policy mode, train/eval/strict caps 32/16/16, max steps 8, decoder CE 0, denoise CE 0, runtime false, no checkpoint export, and full telemetry artifact gate.",
        "",
        "Forbidden at the live stage: decoder CE, denoise CE, runtime, source/body emission, Gemma, harness/scoring, checkpoint export, promotion, `/arxiv` walk, commit inventory reads, and data mining.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8895 Stage8890 Live Authorization Checklist"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8895 records the exact checklist required before any future Stage8890 live one-run structured-policy probe ticket. It remains no-execution/no-training and opens no authority.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
