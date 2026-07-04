#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs/software_maintainer/additional_support_modules_recovery_index_stage8656.json"
SUMMARY = ROOT / "runs/summaries/stage8656_additional_support_modules_recovery_index.json"
DOC = ROOT / "docs/ADDITIONAL_SUPPORT_MODULES_RECOVERY_INDEX_STAGE8656.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}

COMPONENTS: dict[str, dict[str, Any]] = {
    "hybrid_retrieval_fusion": {
        "pipeline_phase": "evidence_retrieval",
        "role": "Fuse lexical, dense, and reranker evidence so graph/symbol objectives do not depend on one fragile retrieval channel.",
        "outputs": ["bm25_score", "dense_score", "rerank_score", "rrf_rank", "mmr_diversity", "evidence_source_ids"],
        "local_status": "references_recovered_not_integrated",
        "recovered_refs": [
            "/arxiv/repositories/camel-ai__camel/camel/retrievers/bm25_retriever.py",
            "/arxiv/repositories/camel-ai__camel/camel/retrievers/vector_retriever.py",
            "/arxiv/repositories/camel-ai__camel/test/retrievers/test_hybrid_retriever.py",
            "/arxiv/repositories/RAG_Techniques/all_rag_techniques_runnable_scripts/fusion_retrieval.py",
            "/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/joiners/documentjoiner.mdx",
        ],
        "next": "Build no-authority retrieval fusion card before source-backed graph/symbol manifests.",
    },
    "query_expansion_rewriter": {
        "pipeline_phase": "evidence_retrieval",
        "role": "Generate controlled alternate search queries from intent, symbol, error, and API hints without leaking target labels.",
        "outputs": ["query_variants", "query_source_bits", "expansion_reason"],
        "local_status": "reference_recovered_not_integrated",
        "recovered_refs": [
            "/arxiv/repositories/RAG_Techniques/all_rag_techniques_runnable_scripts/adaptive_retrieval.py",
            "/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/query/queryexpander.mdx",
        ],
        "next": "Add query-expansion rows only after shortcut audit proves expansions do not encode target labels.",
    },
    "lost_in_middle_context_ranker": {
        "pipeline_phase": "context_packing",
        "role": "Order retrieved evidence into a bounded context window so high-value source spans are not buried in the middle.",
        "outputs": ["packed_context_order", "window_priority", "dropped_span_reason"],
        "local_status": "not_implemented",
        "recovered_refs": [
            "/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/rankers/lostinthemiddleranker.mdx",
            "/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/retrievers/sentencewindowretrieval.mdx",
        ],
        "next": "Create context-packing audit with evidence-present/evidence-dropped counterfactual rows.",
    },
    "source_provenance_license_security_filter": {
        "pipeline_phase": "source_ingestion",
        "role": "Filter mined corpus rows by source lineage, license/security metadata, and allowed import provenance before curriculum admission.",
        "outputs": ["source_license", "security_policy_present", "allowed_import_source", "provenance_hash"],
        "local_status": "missing_for_1m_scale",
        "recovered_refs": [
            "/arxiv/repositories/CheatSheetSeries/cheatsheets/Software_Supply_Chain_Security_Cheat_Sheet.md",
            "/arxiv/repositories/CheatSheetSeries/cheatsheets/AI_Agent_Security_Cheat_Sheet.md",
            "/arxiv/repositories/modelcontextprotocol__servers/SECURITY.md",
        ],
        "next": "Make source lineage mandatory for all 1m+ expansion manifests.",
    },
    "secret_pii_leak_detector": {
        "pipeline_phase": "source_ingestion_and_output_safety",
        "role": "Reject or redact secrets/PII in raw mined data, model-visible context, decoder targets, and final rendered outputs.",
        "outputs": ["secret_pattern_bits", "pii_pattern_bits", "redaction_route", "leak_block_reason"],
        "local_status": "not_implemented_as_first_class_gate",
        "recovered_refs": [
            "/arxiv/repositories/CheatSheetSeries/cheatsheets/Secrets_Management_Cheat_Sheet.md",
            "/arxiv/repositories/CheatSheetSeries/cheatsheets/RAG_Security_Cheat_Sheet.md",
        ],
        "next": "Wire as a pre-judge corpus gate and a post-render gate before any source/body path opens.",
    },
    "dedup_near_duplicate_minhash": {
        "pipeline_phase": "dataset_quality",
        "role": "Detect exact, semantic-key, and near-duplicate rows across train/eval/strict splits to avoid leakage and overcounted scale.",
        "outputs": ["exact_hash", "semantic_key", "near_duplicate_cluster", "split_overlap_flag"],
        "local_status": "partially_implemented_needs_near_duplicate_layer",
        "recovered_refs": [
            "configs/software_maintainer/action_feature_registry.json",
            "/arxiv/agentkernel_recovery/recovered_objective_builders_8630_8639/stage8638_patch_operator_neutral_manifest/build_stage8638_patch_operator_neutral_manifest.py",
        ],
        "next": "Add MinHash/simhash neighbor checks to every scale-manifest gate.",
    },
    "schema_drift_detector": {
        "pipeline_phase": "feature_surface_stability",
        "role": "Detect old/new feature naming drift before model/controller handoff; Stage8058 failed until this was normalized.",
        "outputs": ["feature_alias_map", "unknown_feature_keys", "canonical_feature_keys", "alias_parity_pass"],
        "local_status": "lesson_recovered_not_generalized",
        "recovered_refs": [
            "runs/summaries/stage8060_v27_post_gap_controller_reentry_readiness.json",
            "configs/software_maintainer/action_feature_registry.json",
        ],
        "next": "Make alias parity a hard gate before every controller, graph, symbol, and decoder manifest.",
    },
    "golden_locked_eval_suite": {
        "pipeline_phase": "evaluation",
        "role": "Maintain locked regression/hidden-style eval slices that are never mined back into training data.",
        "outputs": ["locked_eval_id", "regression_slice", "promotion_delta", "leakage_boundary"],
        "local_status": "missing_as_central_contract",
        "recovered_refs": [
            "/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py",
            "/arxiv/repositories/Aider-AI__aider/benchmark/swe_bench.py",
            "/arxiv/datasets/ScaleAI--SWE-Atlas-QnA/rubric_evaluation_config.yaml",
        ],
        "next": "Define fixed promotion/regression slices separate from dev-failure mining pools.",
    },
    "rubric_llm_judge_calibrator": {
        "pipeline_phase": "evaluation_and_dataset_judge",
        "role": "Use rubrics and verifier disagreement as calibration signals, not as sole truth labels.",
        "outputs": ["rubric_score", "judge_confidence", "verifier_disagreement", "manual_review_route"],
        "local_status": "concept_recovered_needs_calibration_gate",
        "recovered_refs": [
            "/arxiv/datasets/ScaleAI--SWE-Atlas-QnA/rubric_evaluation_config.yaml",
            "configs/software_maintainer/action_feature_registry.json",
        ],
        "next": "Require judge/verifier disagreement accounting for any synthetic expansion or teacher label.",
    },
    "static_analysis_security_scanner": {
        "pipeline_phase": "symbolic_verification",
        "role": "Run syntax, AST, import, lint/type/security feature extraction without executing untrusted code.",
        "outputs": ["syntax_ok", "import_allowed", "unsafe_pattern_bits", "static_failure_type"],
        "local_status": "partially_implemented_scaffold",
        "recovered_refs": [
            "/arxiv/TOLBERT_BRAIN/scripts/code_graph.py",
            "/arxiv/repositories/CheatSheetSeries/cheatsheets/AI_Agent_Security_Cheat_Sheet.md",
        ],
        "next": "Unify static analyzer outputs into the dataset judge route card.",
    },
    "coverage_test_selection": {
        "pipeline_phase": "verification_planning",
        "role": "Map changed symbols to likely tests using coverage and repo graph features before runtime is opened.",
        "outputs": ["symbol_coverage", "test_candidate_ids", "coverage_gap", "targeted_test_plan"],
        "local_status": "reference_recovered_not_integrated",
        "recovered_refs": [
            "/arxiv/TOLBERT_BRAIN/scripts/code_graph.py",
            "/arxiv/repositories/Aider-AI__aider/benchmark/swe_bench.py",
        ],
        "next": "Add no-execution coverage/test-selection cards for symbol-binding and patch-operator objectives.",
    },
    "flaky_test_detector": {
        "pipeline_phase": "verification_planning",
        "role": "Separate model/patch failures from unstable test outcomes before training failure labels are emitted.",
        "outputs": ["flake_signature", "rerun_needed", "failure_stability", "route_to_holdout"],
        "local_status": "missing",
        "recovered_refs": [
            "/arxiv/repositories/Aider-AI__aider/benchmark/test_benchmark.py",
            "/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py",
        ],
        "next": "Add failure-stability metadata before using runtime failures as repair labels.",
    },
    "patch_minimality_complexity_meter": {
        "pipeline_phase": "patch_quality",
        "role": "Score candidate edits for minimality, locality, complexity growth, and public API risk.",
        "outputs": ["diff_size", "files_changed", "complexity_delta", "public_api_touch", "minimality_score"],
        "local_status": "not_implemented_as_unified_gate",
        "recovered_refs": [
            "/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py",
            "/arxiv/repositories/OpenAutoCoder__Agentless",
        ],
        "next": "Make minimality a patch-head and verifier-repair gate before body emission is reopened.",
    },
    "cost_budget_scheduler": {
        "pipeline_phase": "agent_control",
        "role": "Control token, retrieval, tool-call, and test budgets as part of the transition policy.",
        "outputs": ["budget_ok", "budget_class", "tool_call_budget", "decoder_budget_ok", "stop_or_retrieve_route"],
        "local_status": "partially_implemented_needs_scheduler",
        "recovered_refs": [
            "/arxiv/agentkernel_recovery/stage8629_recovery_completion_queue/recovery_completion_queue.json",
            "configs/software_maintainer/action_feature_registry.json",
        ],
        "next": "Convert budget evidence cards into an explicit scheduler/ranker module.",
    },
    "memory_retrieval_evaluator": {
        "pipeline_phase": "agent_memory",
        "role": "Evaluate whether stored traces/skills are useful, stale, duplicated, or contaminating heldout objectives.",
        "outputs": ["memory_hit_quality", "staleness", "memory_contamination_flag", "skill_reuse_score"],
        "local_status": "reference_recovered_not_integrated",
        "recovered_refs": [
            "/arxiv/repositories/Agent_Memory_Techniques/all_techniques/28_memory_evaluation/memory_evaluation.ipynb",
            "/arxiv/repositories/Agent_Memory_Techniques/all_techniques/29_memory_benchmarks_LoCoMo/memory_benchmarks_locomo.ipynb",
        ],
        "next": "Add memory quality gates before promoting mined traces into reusable skills.",
    },
    "drift_canary_regression_monitor": {
        "pipeline_phase": "training_governance",
        "role": "Track whether new stages solve new gaps while preserving older 5k/6k/7k/8k lessons.",
        "outputs": ["canary_slice", "regression_delta", "forgotten_skill", "promotion_block_reason"],
        "local_status": "missing_as_first_class_monitor",
        "recovered_refs": [
            "runs/local/artifacts/reconstructed_stage_registry.json",
            "/arxiv/agentkernel_recovery/stage8624_central_graph_recovery/docs/CENTRAL_RESEARCH_GRAPH_STAGE8622.md",
        ],
        "next": "Create cross-spine canaries from recovered stage clusters before scale expansion.",
    },
    "active_learning_uncertainty_sampler": {
        "pipeline_phase": "curriculum_expansion",
        "role": "Prioritize new rows from uncertain/high-margin-conflict cells rather than bulk random mining.",
        "outputs": ["uncertainty_score", "margin", "entropy", "sample_priority", "cell_gap"],
        "local_status": "not_implemented",
        "recovered_refs": [
            "configs/software_maintainer/support_systems_recovery_index_stage8653.json",
            "configs/software_maintainer/action_feature_registry.json",
        ],
        "next": "Use Stage7923-style confidence/margin diagnostics to drive 1m expansion cells.",
    },
    "weak_supervision_label_model": {
        "pipeline_phase": "dataset_labeling",
        "role": "Combine heuristic, verifier, teacher, retrieval, and judge votes into calibrated labels with abstain routes.",
        "outputs": ["label_votes", "label_confidence", "conflict_reason", "abstain_route"],
        "local_status": "missing",
        "recovered_refs": [
            "configs/software_maintainer/action_feature_registry.json",
            "scripts/objective_row_judge.py",
        ],
        "next": "Add label-model manifest before accepting large synthetic/teacher-mined labels.",
    },
    "mutation_adversarial_test_generator": {
        "pipeline_phase": "hard_negative_generation",
        "role": "Create adversarial corruptions, wrong imports, wrong symbols, and near-miss patches that force robust transition learning.",
        "outputs": ["mutation_type", "expected_guard", "hard_negative_pair", "repair_target"],
        "local_status": "concept_recovered_needs_tooling",
        "recovered_refs": [
            "/arxiv/agentkernel_recovery/recovered_objective_builders_8630_8639/stage8638_patch_operator_neutral_manifest/build_stage8638_patch_operator_neutral_manifest.py",
            "/arxiv/repositories/Aider-AI__aider/benchmark/benchmark.py",
        ],
        "next": "Generate paired counterfactual rows for every active transition cell.",
    },
    "source_inventory_lineage_tracker": {
        "pipeline_phase": "source_ingestion",
        "role": "Record source origin, hash, license, split eligibility, and transformation lineage for every mined row.",
        "outputs": ["source_id", "content_hash", "transform_chain", "split_eligibility", "lineage_card"],
        "local_status": "planned_stage8655a_not_built",
        "recovered_refs": [
            "configs/software_maintainer/source_backed_graph_symbol_binding_recovery_plan_stage8655.json",
            "/arxiv/TOLBERT_BRAIN/data/repos/nodes_repos.jsonl",
            "/arxiv/TOLBERT_BRAIN/data/repos/spans_repos.jsonl",
        ],
        "next": "Implement Stage8655a as a reusable lineage tracker, not a one-off inventory.",
    },
    "eval_harness_metrics_reporter": {
        "pipeline_phase": "evaluation",
        "role": "Standardize benchmark/run metrics so frontier comparisons are factual and not narrative-only.",
        "outputs": ["metric_card", "slice_pass_rate", "failure_cluster", "artifact_paths", "promotion_decision"],
        "local_status": "fragmented_across_stage_summaries",
        "recovered_refs": [
            "/arxiv/TOLBERT_BRAIN/scripts/eval_flat_baseline.py",
            "/arxiv/TOLBERT_BRAIN/scripts/eval_hierarchical_classification.py",
            "/arxiv/TOLBERT_BRAIN/scripts/eval_zero_shot_cross_domain.py",
            "/arxiv/TOLBERT_BRAIN/scripts/eval_retrieval.py",
        ],
        "next": "Use one metric-card schema across support modules, objectives, and training probes.",
    },
    "contamination_leakage_detector": {
        "pipeline_phase": "dataset_quality",
        "role": "Detect target leakage, heldout contamination, label-coded IDs, direct target fields, and source/body leakage.",
        "outputs": ["target_leak_flag", "heldout_overlap", "label_coded_id", "body_leak_flag", "contamination_route"],
        "local_status": "implemented_in_many_audits_needs_unified_module",
        "recovered_refs": [
            "scripts/shortcut_baseline_audit.py",
            "scripts/objective_row_judge.py",
            "configs/software_maintainer/action_feature_registry.json",
        ],
        "next": "Consolidate shortcut/leak audits into a shared library used by all builders.",
    },
    "context_window_packer": {
        "pipeline_phase": "context_packing",
        "role": "Compress and arrange evidence from repo graph, retrieval, source spans, memory, and task state under fixed encoder limits.",
        "outputs": ["context_budget", "span_priority", "packed_slots", "compression_reason", "dropped_evidence"],
        "local_status": "missing",
        "recovered_refs": [
            "/arxiv/repositories/deepset-ai__haystack/docs-website/docs/pipeline-components/retrievers/sentencewindowretrieval.mdx",
            "/arxiv/TOLBERT_BRAIN/scripts/split_spans_by_paragraph.py",
        ],
        "next": "Build context-packing rows that teach retrieve/compress/drop decisions before long-context model work.",
    },
    "tool_action_trajectory_analyzer": {
        "pipeline_phase": "agent_trace_learning",
        "role": "Convert SWE-agent/Aider/Open-SWE traces into observe-orient-act transition labels and failure diagnoses.",
        "outputs": ["action_sequence", "phase_state", "failure_reason", "repair_transition", "trajectory_quality"],
        "local_status": "sources_recovered_not_mined",
        "recovered_refs": [
            "/arxiv/datasets/nvidia--Open-SWE-Traces",
            "/arxiv/repositories/SWE-agent__SWE-agent",
            "/arxiv/repositories/Aider-AI__aider",
        ],
        "next": "Mine traces into finite action/state rows only after lineage and leakage gates pass.",
    },
}


def main() -> None:
    existing = ROOT / "configs/software_maintainer/support_systems_recovery_index_stage8653.json"
    existing_components = set()
    if existing.exists():
        existing_components = set(json.loads(existing.read_text(encoding="utf-8")).get("components", {}))
    overlap = sorted(existing_components & set(COMPONENTS))
    missing_refs = {
        name: [ref for ref in comp.get("recovered_refs", []) if ref.startswith("/") and not Path(ref).exists()]
        for name, comp in COMPONENTS.items()
    }
    missing_refs = {k: v for k, v in missing_refs.items() if v}
    card = {
        "stage": 8656,
        "stage_name": "stage8656_additional_support_modules_recovery_index",
        "passed": not overlap,
        "authority": AUTHORITY_CLOSED,
        "components": COMPONENTS,
        "metrics": {
            "additional_support_components": len(COMPONENTS),
            "overlap_with_stage8653": overlap,
            "missing_recovered_refs": missing_refs,
            "pipeline_phases": sorted({c["pipeline_phase"] for c in COMPONENTS.values()}),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "decision": "Recovered additional support modules that are necessary for 1m+ scale curriculum expansion, source-backed graph/symbol learning, context packing, eval governance, and safe mining. This is no-authority indexing only.",
        "next_best_step": "Attach Stage8656 modules to the central graph, then implement source inventory, shared feature normalization, retrieval fusion, contamination/leakage, and locked-eval cards before any training reopen.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    OUT.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage8656 Additional Support Modules Recovery Index",
        "",
        "This stage recovers support modules that were not first-class in Stage8653 but are required for the 100M software-maintainer curriculum compiler and 1m+ judged expansion path.",
        "",
        "Authority remains closed: no model execution, no CE training, no runtime, no source/body emission, no Gemma/harness/scoring/promotion.",
        "",
        "## Modules",
    ]
    for name, comp in sorted(COMPONENTS.items()):
        lines.append(f"- `{name}`: {comp['role']} Status: `{comp['local_status']}`. Next: {comp['next']}")
    lines.extend([
        "",
        "## Decision",
        card["decision"],
        "",
        "## Next Step",
        card["next_best_step"],
    ])
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
