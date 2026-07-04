# Stage8656 Additional Support Modules Recovery Index

This stage recovers support modules that were not first-class in Stage8653 but are required for the 100M software-maintainer curriculum compiler and 1m+ judged expansion path.

Authority remains closed: no model execution, no CE training, no runtime, no source/body emission, no Gemma/harness/scoring/promotion.

## Modules
- `active_learning_uncertainty_sampler`: Prioritize new rows from uncertain/high-margin-conflict cells rather than bulk random mining. Status: `not_implemented`. Next: Use Stage7923-style confidence/margin diagnostics to drive 1m expansion cells.
- `contamination_leakage_detector`: Detect target leakage, heldout contamination, label-coded IDs, direct target fields, and source/body leakage. Status: `implemented_in_many_audits_needs_unified_module`. Next: Consolidate shortcut/leak audits into a shared library used by all builders.
- `context_window_packer`: Compress and arrange evidence from repo graph, retrieval, source spans, memory, and task state under fixed encoder limits. Status: `missing`. Next: Build context-packing rows that teach retrieve/compress/drop decisions before long-context model work.
- `cost_budget_scheduler`: Control token, retrieval, tool-call, and test budgets as part of the transition policy. Status: `partially_implemented_needs_scheduler`. Next: Convert budget evidence cards into an explicit scheduler/ranker module.
- `coverage_test_selection`: Map changed symbols to likely tests using coverage and repo graph features before runtime is opened. Status: `reference_recovered_not_integrated`. Next: Add no-execution coverage/test-selection cards for symbol-binding and patch-operator objectives.
- `dedup_near_duplicate_minhash`: Detect exact, semantic-key, and near-duplicate rows across train/eval/strict splits to avoid leakage and overcounted scale. Status: `partially_implemented_needs_near_duplicate_layer`. Next: Add MinHash/simhash neighbor checks to every scale-manifest gate.
- `drift_canary_regression_monitor`: Track whether new stages solve new gaps while preserving older 5k/6k/7k/8k lessons. Status: `missing_as_first_class_monitor`. Next: Create cross-spine canaries from recovered stage clusters before scale expansion.
- `eval_harness_metrics_reporter`: Standardize benchmark/run metrics so frontier comparisons are factual and not narrative-only. Status: `fragmented_across_stage_summaries`. Next: Use one metric-card schema across support modules, objectives, and training probes.
- `flaky_test_detector`: Separate model/patch failures from unstable test outcomes before training failure labels are emitted. Status: `missing`. Next: Add failure-stability metadata before using runtime failures as repair labels.
- `golden_locked_eval_suite`: Maintain locked regression/hidden-style eval slices that are never mined back into training data. Status: `missing_as_central_contract`. Next: Define fixed promotion/regression slices separate from dev-failure mining pools.
- `hybrid_retrieval_fusion`: Fuse lexical, dense, and reranker evidence so graph/symbol objectives do not depend on one fragile retrieval channel. Status: `references_recovered_not_integrated`. Next: Build no-authority retrieval fusion card before source-backed graph/symbol manifests.
- `lost_in_middle_context_ranker`: Order retrieved evidence into a bounded context window so high-value source spans are not buried in the middle. Status: `not_implemented`. Next: Create context-packing audit with evidence-present/evidence-dropped counterfactual rows.
- `memory_retrieval_evaluator`: Evaluate whether stored traces/skills are useful, stale, duplicated, or contaminating heldout objectives. Status: `reference_recovered_not_integrated`. Next: Add memory quality gates before promoting mined traces into reusable skills.
- `mutation_adversarial_test_generator`: Create adversarial corruptions, wrong imports, wrong symbols, and near-miss patches that force robust transition learning. Status: `concept_recovered_needs_tooling`. Next: Generate paired counterfactual rows for every active transition cell.
- `patch_minimality_complexity_meter`: Score candidate edits for minimality, locality, complexity growth, and public API risk. Status: `not_implemented_as_unified_gate`. Next: Make minimality a patch-head and verifier-repair gate before body emission is reopened.
- `query_expansion_rewriter`: Generate controlled alternate search queries from intent, symbol, error, and API hints without leaking target labels. Status: `reference_recovered_not_integrated`. Next: Add query-expansion rows only after shortcut audit proves expansions do not encode target labels.
- `rubric_llm_judge_calibrator`: Use rubrics and verifier disagreement as calibration signals, not as sole truth labels. Status: `concept_recovered_needs_calibration_gate`. Next: Require judge/verifier disagreement accounting for any synthetic expansion or teacher label.
- `schema_drift_detector`: Detect old/new feature naming drift before model/controller handoff; Stage8058 failed until this was normalized. Status: `lesson_recovered_not_generalized`. Next: Make alias parity a hard gate before every controller, graph, symbol, and decoder manifest.
- `secret_pii_leak_detector`: Reject or redact secrets/PII in raw mined data, model-visible context, decoder targets, and final rendered outputs. Status: `not_implemented_as_first_class_gate`. Next: Wire as a pre-judge corpus gate and a post-render gate before any source/body path opens.
- `source_inventory_lineage_tracker`: Record source origin, hash, license, split eligibility, and transformation lineage for every mined row. Status: `planned_stage8655a_not_built`. Next: Implement Stage8655a as a reusable lineage tracker, not a one-off inventory.
- `source_provenance_license_security_filter`: Filter mined corpus rows by source lineage, license/security metadata, and allowed import provenance before curriculum admission. Status: `missing_for_1m_scale`. Next: Make source lineage mandatory for all 1m+ expansion manifests.
- `static_analysis_security_scanner`: Run syntax, AST, import, lint/type/security feature extraction without executing untrusted code. Status: `partially_implemented_scaffold`. Next: Unify static analyzer outputs into the dataset judge route card.
- `tool_action_trajectory_analyzer`: Convert SWE-agent/Aider/Open-SWE traces into observe-orient-act transition labels and failure diagnoses. Status: `sources_recovered_not_mined`. Next: Mine traces into finite action/state rows only after lineage and leakage gates pass.
- `weak_supervision_label_model`: Combine heuristic, verifier, teacher, retrieval, and judge votes into calibrated labels with abstain routes. Status: `missing`. Next: Add label-model manifest before accepting large synthetic/teacher-mined labels.

## Decision
Recovered additional support modules that are necessary for 1m+ scale curriculum expansion, source-backed graph/symbol learning, context packing, eval governance, and safe mining. This is no-authority indexing only.

## Next Step
Attach Stage8656 modules to the central graph, then implement source inventory, shared feature normalization, retrieval fusion, contamination/leakage, and locked-eval cards before any training reopen.
