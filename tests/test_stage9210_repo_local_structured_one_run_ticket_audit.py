from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    path = root / "scripts/build_stage9210_repo_local_structured_one_run_ticket_audit.py"
    spec = importlib.util.spec_from_file_location("stage9210_audit", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_negative_cases_cover_execution_and_arxiv():
    mod = _load()
    ticket = {
        "execution_authorized_now": False,
        "command_materialized": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(mod.DENIED_NOW_OPERATIONS),
        "authority": dict(mod.AUTHORITY_CLOSED),
        "future_output_dir": str(mod.ROOT / "runs/local/probes/example"),
        "required_limits": {"decoder_ce_weight": 0.0},
    }
    case_names = {case["case"] for case in mod.negative_cases(ticket)}
    assert "execution_authorized_now_true" in case_names
    assert "command_materialized_true" in case_names
    assert "future_output_dir_arxiv" in case_names
    assert "decoder_ce_weight_opened" in case_names


def test_all_negative_results_must_be_rejected_shape():
    mod = _load()
    ticket = {
        "ticket_status": "DESIGN_ONLY_INACTIVE",
        "execution_authorized_now": False,
        "command_materialized": False,
        "allowed_operations_now": [],
        "denied_operations_now": list(mod.DENIED_NOW_OPERATIONS),
        "authority": dict(mod.AUTHORITY_CLOSED),
        "future_output_dir": str(mod.ROOT / "runs/local/probes/example"),
        "required_limits": {
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
            "final_checkpoint_export": False,
        },
        "required_before_execution": [
            "explicit_user_one_run_request",
            "fresh_pre_execution_audit_passed_after_ticket",
            "manifest_path_audit_passed",
            "loss_mask_enforcement_runtime_assertions",
            "telemetry_artifact_gate_required",
            "safe_cleanup_marker_and_dry_run_passed",
            "post_run_stage8902_diagnostics_required",
            "stage8903_diagnostics_closure_required",
            "no_final_checkpoint_export",
        ],
        "source_manifest_path": str(
            mod.ROOT
            / "runs/local/artifacts/stage9206_repo_local_three_family_selector/stage8937_structured_policy_bundle/materialization_preview/trainer_rows.jsonl"
        ),
        "post_run_diagnostic_gate_required": True,
        "post_run_diagnostic_gate_stage": "stage8902_diagnostic_promotion_gate",
        "post_run_artifact_contract_stage": "stage8862_native_probe_interpretability_artifact_contract",
        "diagnostic_closure_stage": "stage8903_diagnostics_closure_audit",
        "promotion_blocked_until_diagnostics_pass": True,
        "metrics_interpretation_blocked_until_diagnostics_pass": True,
        "forbidden_without_passing_diagnostics": [
            "interpret_model_metrics",
            "claim_training_quality",
            "claim_decoder_quality",
            "promote_probe",
            "export_checkpoint",
            "merge_controller",
            "open_runtime",
            "open_source_or_body_emission",
            "use_hidden_or_locked_eval_for_tuning",
        ],
    }
    review = {"mode": "structured_policy_probe", "review_failures": []}
    results = mod.run_negative_cases(ticket, {"passed": True}, {"passed": True}, review)
    assert results
    assert all(item["rejected"] for item in results)
