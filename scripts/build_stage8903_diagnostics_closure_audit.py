#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8903
NAME = "stage8903_diagnostics_closure_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DIAGNOSTICS_CLOSURE_AUDIT_STAGE8903.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"

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

REQUIRED_SUMMARIES = {
    "telemetry_gap_audit": "runs/summaries/stage8858_model_interpretability_telemetry_gap_audit.json",
    "native_probe_artifact_contract": "runs/summaries/stage8862_native_probe_interpretability_artifact_contract.json",
    "telemetry_gate_matrix": "runs/summaries/stage8893_no_execution_telemetry_gate_matrix.json",
    "transition_schema_contract": "runs/summaries/stage8899_verified_transition_record_schema_contract.json",
    "transition_validation_contract": "runs/summaries/stage8900_verified_transition_record_validation_contract.json",
    "no_mining_compiler_adapter": "runs/summaries/stage8901_verified_transition_record_no_mining_compiler_adapter.json",
    "diagnostic_promotion_gate": "runs/summaries/stage8902_diagnostic_promotion_gate.json",
}

REQUIRED_TESTS = {
    "tests/test_native_probe_interpretability_artifact_contract.py": [
        "test_structured_artifact_contract_passes_schema_complete_outputs",
        "test_artifact_contract_fails_empty_jsonl",
        "test_bounded_artifact_contract_requires_real_token_positions",
    ],
    "tests/test_diagnostic_promotion_gate.py": [
        "test_structured_diagnostic_promotion_gate_accepts_complete_artifacts",
        "test_structured_diagnostic_promotion_gate_rejects_decoder_delta",
        "test_diagnostic_promotion_gate_rejects_missing_artifact",
    ],
    "tests/test_training_telemetry_metrics.py": [
        "high_confidence_wrong",
        "token_loss_map",
    ],
    "tests/test_gradient_activation_interpretability.py": [
        "row_gradient_norm",
        "activation_patch",
        "feature_ablation",
    ],
    "tests/test_dataset_cartography_active_learning.py": [
        "forgetting_events",
        "active_learning",
    ],
    "tests/test_training_data_attribution_influence.py": [
        "helpful",
        "harmful",
        "missing_neighborhood",
    ],
    "tests/test_verified_transition_record_schema_contract.py": [
        "state_before",
        "verifier_result",
        "loss_mask",
    ],
    "tests/test_verified_transition_record_validation_contract.py": [
        "test_example_record_is_complete_closed_schema_only",
        "test_forbidden_visible_field_fails_validation",
    ],
}

CLOSURE_DIMENSIONS = [
    "data_quality_and_junk_ood",
    "source_lineage_provenance_leakage",
    "locked_eval_and_drift",
    "schema_and_gate_status",
    "row_field_logits_confidence_entropy",
    "row_field_losses_and_confusion",
    "token_loss_maps_for_decoder",
    "row_gradient_norms",
    "activation_summaries",
    "feature_ablation_attribution",
    "activation_patch_recovery",
    "row_dynamics_forgetting",
    "artifact_contract_validation",
    "promotion_blocker",
]

STILL_REQUIRES_REAL_RUN_ARTIFACTS = [
    "actual_row_field_logits_jsonl",
    "actual_row_field_losses_jsonl",
    "actual_row_gradient_norms_jsonl",
    "actual_activation_summary_jsonl",
    "actual_feature_ablation_attribution_jsonl",
    "actual_activation_patch_recovery_jsonl",
    "actual_row_dynamics_history_jsonl",
    "actual_structured_confusion_matrix_json",
    "actual_row_token_loss_jsonl_for_decoder_claims",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def text_has_markers(path: Path, markers: list[str]) -> tuple[bool, list[str]]:
    if not path.exists():
        return False, markers
    text = path.read_text(encoding="utf-8")
    missing = [marker for marker in markers if marker not in text]
    return not missing, missing


def closure_audit(registry: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    summary_checks = []
    for name, rel in REQUIRED_SUMMARIES.items():
        path = ROOT / rel
        card = load_json(path)
        ok = path.exists() and card.get("passed") is True and not any((card.get("authority") or {}).values())
        summary_checks.append({"name": name, "path": rel, "passed": ok})
        if not path.exists():
            failures.append(f"missing_summary:{name}")
        elif card.get("passed") is not True:
            failures.append(f"summary_failed:{name}")
        elif any((card.get("authority") or {}).values()):
            failures.append(f"summary_authority_open:{name}")
    test_checks = []
    for rel, markers in REQUIRED_TESTS.items():
        ok, missing = text_has_markers(ROOT / rel, markers)
        test_checks.append({"path": rel, "passed": ok, "missing_markers": missing})
        if not ok:
            failures.append(f"missing_test_markers:{rel}:{','.join(missing)}")
    authority_counts = (registry.get("metrics") or {}).get("authority_counts") or {}
    latest = int((registry.get("metrics") or {}).get("latest_stage", -1))
    if latest not in {8902, STAGE, 8904}:
        failures.append(f"unexpected_registry_frontier:{latest}")
    if any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED):
        failures.append("registry_authority_counts_nonzero")
    return {
        "passed": not failures,
        "failures": failures,
        "summary_checks": summary_checks,
        "test_checks": test_checks,
        "closure_dimensions": CLOSURE_DIMENSIONS,
        "still_requires_real_run_artifacts": STILL_REQUIRES_REAL_RUN_ARTIFACTS,
        "summaries_checked": len(summary_checks),
        "summaries_passing": sum(1 for item in summary_checks if item["passed"]),
        "test_files_checked": len(test_checks),
        "test_files_passing": sum(1 for item in test_checks if item["passed"]),
        "registry_latest_stage_before_update": latest,
        "registry_authority_counts_zero": not any(authority_counts.get(key, 0) != 0 for key in AUTHORITY_CLOSED),
    }


def main() -> None:
    registry = load_json(REGISTRY) or {"rows": [], "metrics": {}}
    audit = closure_audit(registry)
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": audit["passed"],
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "failures": audit["failures"],
            "closure_dimensions": len(CLOSURE_DIMENSIONS),
            "summaries_checked": audit["summaries_checked"],
            "summaries_passing": audit["summaries_passing"],
            "test_files_checked": audit["test_files_checked"],
            "test_files_passing": audit["test_files_passing"],
            "still_requires_real_run_artifacts": len(STILL_REQUIRES_REAL_RUN_ARTIFACTS),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "promotion_ready": False,
        },
        "summary_checks": audit["summary_checks"],
        "test_checks": audit["test_checks"],
        "closure_dimensions": CLOSURE_DIMENSIONS,
        "still_requires_real_run_artifacts": STILL_REQUIRES_REAL_RUN_ARTIFACTS,
        "decision": "Diagnostics are closed for no-execution readiness: contracts, tests, artifact audits, and promotion blockers exist. Real model claims still require actual run artifacts." if audit["passed"] else "Diagnostics closure audit failed.",
        "next_best_step": "Stop diagnostics hardening unless adding a new diagnostic family. A future authorized probe must emit all required artifacts and pass Stage8902 before metrics are interpreted.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8903 Diagnostics Closure Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Diagnostics are closed for no-execution readiness. This means contracts, tests, artifact audits, and promotion blockers exist before any future probe/training claim.",
        "",
        "It does not mean model quality is proven. Real claims still require actual run artifacts: row-field logits/losses, gradient norms, activation summaries, feature ablations, activation patch recovery, row dynamics, confusion matrices, and decoder token-loss maps when decoder CE is in scope.",
        "",
        "This opens no model execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, controller merge, checkpoint export, or promotion.",
        "",
    ]), encoding="utf-8")
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") != NAME]
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = card["passed"]
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    marker = "## Stage8903 Diagnostics Closure Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8903 closes diagnostics for no-execution readiness. It verifies the telemetry substrate, native artifact contract, no-execution telemetry gate matrix, verified-transition schema/validation/compiler adapter, and diagnostic promotion gate are all present and authority-closed.",
            "",
            "This is not a model-quality claim. Any future probe must still emit real diagnostics and pass Stage8902 before metrics can be interpreted.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
