#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8753
NAME = "stage8753_parallel_recovery_gap_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "PARALLEL_RECOVERY_GAP_AUDIT_STAGE8753.md"

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

MODULES: dict[str, dict[str, Any]] = {
    # Already recovered after stale index docs.
    "cluster_slice_near_duplicate_detector": {"files": ["scripts/cluster_slice_near_duplicate_detector.py", "tests/test_cluster_slice_near_duplicate_detector.py", "runs/summaries/stage8682_cluster_slice_detector_readiness.json"], "class": "recovered_ready"},
    "dataset_cartography_active_learning": {"files": ["scripts/dataset_cartography_active_learning.py", "tests/test_dataset_cartography_active_learning.py", "runs/summaries/stage8723_dataset_cartography_active_learning_readiness.json"], "class": "recovered_ready"},
    "training_data_attribution_influence": {"files": ["scripts/training_data_attribution_influence.py", "tests/test_training_data_attribution_influence.py", "runs/summaries/stage8725_training_data_attribution_influence_readiness.json"], "class": "recovered_ready"},
    "context_packer_lost_in_middle_memory_retrieval": {"files": ["scripts/context_packer_v1.py", "runs/summaries/stage8694_context_packer_lost_in_middle_readiness.json", "runs/summaries/stage8695_context_packer_graph_attachment.json"], "class": "recovered_partial"},
    "training_telemetry": {"files": ["scripts/training_telemetry.py", "scripts/training_telemetry_metrics.py", "runs/summaries/stage8696_training_telemetry_metrics_readiness.json", "runs/summaries/stage8697_training_telemetry_graph_attachment.json"], "class": "recovered_partial"},
    "gradient_activation_interpretability": {"files": ["scripts/gradient_activation_interpretability.py", "runs/summaries/stage8710_gradient_activation_interpretability_readiness.json", "runs/summaries/stage8711_gradient_activation_interpretability_graph_attachment.json"], "class": "recovered_partial"},
    "confidence_calibration_ood_heads": {"files": ["scripts/confidence_ood_head_contract.py", "tests/test_confidence_ood_head_contract.py", "runs/summaries/stage8735_confidence_ood_head_contract_readiness.json"], "class": "recovered_partial"},
    "state_space_repo_state_compressor": {"files": ["scripts/state_space_repo_state_compressor.py", "runs/summaries/stage8708_state_space_repo_state_compressor_readiness.json", "runs/summaries/stage8709_state_space_repo_state_compressor_graph_attachment.json"], "class": "recovered_partial"},
    "repo_graph_encoder": {"files": ["scripts/repo_graph_encoder.py", "runs/summaries/stage8714_repo_graph_encoder_readiness.json", "runs/summaries/stage8715_repo_graph_encoder_graph_attachment.json"], "class": "recovered_partial"},
    "runtime_verifier_loop_contract": {"files": ["scripts/runtime_verifier_loop_contract.py", "runs/summaries/stage8701_runtime_verifier_loop_contract_readiness.json", "runs/summaries/stage8702_runtime_verifier_loop_graph_attachment.json"], "class": "recovered_closed_contract"},
    "contamination_leakage_detector": {"files": ["scripts/contamination_leakage_detector.py", "tests/test_contamination_leakage_detector.py", "runs/summaries/stage8746_contamination_leakage_detector_readiness.json"], "class": "recovered_ready_untracked_concurrent"},
    "golden_locked_eval_suite": {"files": ["scripts/golden_locked_eval_suite.py", "tests/test_golden_locked_eval_suite.py", "runs/summaries/stage8748_golden_locked_eval_suite_readiness.json"], "class": "recovered_ready_untracked_concurrent"},
    "drift_canary_regression_monitor": {"files": ["scripts/drift_canary_regression_monitor.py", "tests/test_drift_canary_regression_monitor.py", "runs/summaries/stage8750_drift_canary_regression_monitor_readiness.json"], "class": "recovered_ready_untracked_concurrent"},

    # Real remaining missing/first-class gaps not covered by the active compiler-gate task.
    "cost_budget_scheduler": {"files": ["scripts/cost_budget_scheduler.py", "tests/test_cost_budget_scheduler.py"], "class": "missing_real", "why": "Budget flags exist in rows, but no reusable scheduler/ranker controls token/tool/test budgets before action selection."},
    "coverage_test_selection": {"files": ["scripts/coverage_test_selection.py", "tests/test_coverage_test_selection.py"], "class": "missing_real", "why": "No no-execution symbol-to-test selection card for source-backed edit/patch/verifier objectives."},
    "flaky_test_detector": {"files": ["scripts/flaky_test_detector.py", "tests/test_flaky_test_detector.py"], "class": "missing_real", "why": "Runtime remains closed, but before repair labels are trusted we need a failure-stability contract."},
    "memory_retrieval_evaluator": {"files": ["scripts/memory_retrieval_evaluator.py", "tests/test_memory_retrieval_evaluator.py"], "class": "missing_real", "why": "No memory quality/staleness/contamination gate before mined traces become reusable skills."},
    "patch_minimality_complexity_meter": {"files": ["scripts/patch_minimality_complexity_meter.py", "tests/test_patch_minimality_complexity_meter.py"], "class": "missing_real", "why": "No unified patch minimality/complexity/public-API-touch gate for future body/patch objectives."},
    "query_expansion_rewriter": {"files": ["scripts/query_expansion_rewriter.py", "tests/test_query_expansion_rewriter.py"], "class": "missing_real", "why": "Retrieval expansion exists as concept, but no shortcut-safe query-expansion row/card generator."},
    "schema_drift_detector": {"files": ["scripts/schema_drift_detector.py", "tests/test_schema_drift_detector.py"], "class": "missing_real", "why": "Feature name drift caused prior failures; no reusable alias/schema parity gate for every manifest builder."},
    "static_analysis_security_scanner": {"files": ["scripts/static_analysis_security_scanner.py", "tests/test_static_analysis_security_scanner.py"], "class": "missing_real", "why": "Security route bits exist, but no unified static scanner output card feeding the dataset judge."},
    "weak_supervision_label_model": {"files": ["scripts/weak_supervision_label_model.py", "tests/test_weak_supervision_label_model.py"], "class": "missing_real", "why": "No label-model manifest before accepting large synthetic/teacher-mined labels."},
    "eval_trace_to_dataset_patch_loop": {"files": ["scripts/eval_trace_to_dataset_patch_loop.py", "tests/test_eval_trace_to_dataset_patch_loop.py"], "class": "missing_real", "why": "No first-class dataset_patch records converting eval failures into add/remove/relabel/rebalance operations."},
    "knowledge_graph_memory_store": {"files": ["scripts/knowledge_graph_memory_store.py", "tests/test_knowledge_graph_memory_store.py"], "class": "missing_real", "why": "Central graph exists, but no durable memory key binding for skills/source facts/tool outcomes."},
    "latency_resource_observability": {"files": ["scripts/latency_resource_observability.py", "tests/test_latency_resource_observability.py"], "class": "missing_real", "why": "Telemetry exists for training, but no unified latency/resource budget observability for controller economics."},
    "repository_universe_builder": {"files": ["scripts/repository_universe_builder.py", "tests/test_repository_universe_builder.py"], "class": "missing_real", "why": "No source-inventory extension building repo/file/symbol similarity universe for 1M+ sampling."},
    "skill_tool_registry": {"files": ["scripts/skill_tool_registry.py", "tests/test_skill_tool_registry.py"], "class": "missing_real", "why": "No tool/action ontology rows for observe-orient-act trajectory training."},
    "traced_eval_observability": {"files": ["scripts/traced_eval_observability.py", "tests/test_traced_eval_observability.py"], "class": "missing_real", "why": "No shared trace schema across dataset judge, eval harness, and curriculum compiler."},
    "ngram_repetition_style_detectors": {"files": ["scripts/ngram_repetition_style_detectors.py", "tests/test_ngram_repetition_style_detectors.py"], "class": "missing_real", "why": "N-gram/Markov style priors are not yet emitted as safe ranker features for decoder/denoise rows."},

    # Objective-builder integration gaps, not generic support modules.
    "source_backed_edit_localization_builder": {"files": ["scripts/source_backed_edit_localization_builder.py"], "class": "integration_needed", "why": "Neutral objective exists; source-backed builder must emit recovered gate_status before scale rows."},
    "source_backed_patch_operator_builder": {"files": ["scripts/source_backed_patch_operator_builder.py"], "class": "integration_needed", "why": "Neutral objective exists; source-backed builder must emit recovered gate_status before scale rows."},
    "source_backed_verifier_repair_builder": {"files": ["scripts/source_backed_verifier_repair_builder.py"], "class": "integration_needed", "why": "Neutral objective exists; source-backed builder must emit recovered gate_status before scale rows."},
    "reservoir_source_sampler": {"files": ["scripts/reservoir_source_sampler.py"], "class": "integration_needed", "why": "1M+ expansion still needs source quotas and sampling cards after gates are wired."},
    "tool_action_trajectory_analyzer": {"files": ["scripts/tool_action_trajectory_analyzer.py"], "class": "integration_needed", "why": "Trace-to-finite-action rows should wait for lineage/leakage gates but the analyzer is still absent."},
}


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for module_id, spec in MODULES.items():
        missing = [rel for rel in spec["files"] if not exists(rel)]
        effective_status = spec["class"]
        if spec["class"].startswith("recovered") and missing:
            effective_status = "recovered_expected_but_missing_files"
        if spec["class"] in {"missing_real", "integration_needed"} and not missing:
            effective_status = "exists_but_needs_readiness_audit"
        records.append({
            "module_id": module_id,
            "classification": spec["class"],
            "effective_status": effective_status,
            "missing_files": missing,
            "files": spec["files"],
            "why": spec.get("why"),
        })
    counts: dict[str, int] = {}
    for row in records:
        counts[row["effective_status"]] = counts.get(row["effective_status"], 0) + 1
    missing_real = [row for row in records if row["effective_status"] == "missing_real"]
    integration_needed = [row for row in records if row["effective_status"] == "integration_needed"]
    recovered_or_stale = [row for row in records if row["effective_status"].startswith("recovered") or row["effective_status"] == "exists_but_needs_readiness_audit"]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "modules_reviewed": len(records),
            "effective_status_counts": counts,
            "missing_real_count": len(missing_real),
            "integration_needed_count": len(integration_needed),
            "recovered_or_stale_doc_count": len(recovered_or_stale),
        },
        "records": records,
        "highest_priority_parallel_recovery": [
            "schema_drift_detector",
            "patch_minimality_complexity_meter",
            "coverage_test_selection",
            "flaky_test_detector",
            "eval_trace_to_dataset_patch_loop",
            "skill_tool_registry",
            "ngram_repetition_style_detectors",
        ],
        "do_not_duplicate_active_work": [
            "semantic_equivalence_metamo rphic_verifier",
            "golden_locked_eval_suite",
            "drift_canary_regression_monitor",
            "stage8752_support_stack_integration_audit",
            "objective_builder_gate_status_patch",
        ],
        "decision": "Parallel recovery search found additional missing support modules outside the active compiler-gate work. Do not resume mining/training until active builder gate_status work and the highest-priority missing support modules are reconciled.",
        "next_best_step": "Recover schema_drift_detector or patch_minimality_complexity_meter in parallel; avoid touching concurrent semantic/golden/drift/support-stack commits.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "parallel_recovery_gap_records.json").write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage8753 Parallel Recovery Gap Audit",
        "",
        "This audit avoids the active compiler-gate/commit reconciliation work and searches for other missing modules needed before mining/training resumes.",
        "",
        f"Modules reviewed: `{len(records)}`",
        f"Missing real modules: `{len(missing_real)}`",
        f"Integration-needed modules: `{len(integration_needed)}`",
        "",
        "## Highest Priority Parallel Recovery",
        "",
    ]
    for item in card["highest_priority_parallel_recovery"]:
        why = next((r.get("why") for r in records if r["module_id"] == item), "")
        lines.append(f"- `{item}`: {why}")
    lines.extend([
        "",
        "## Authority",
        "",
        "No mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized by this audit.",
        "",
    ])
    DOC.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
