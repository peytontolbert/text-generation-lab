# Stage8660 Leakage/Retrieval/Locked-Eval Control Contract

This stage restores the missing control spine around source-backed curriculum expansion. It is documentation/configuration only.

## Source Groups
- `repo_graph_sources`: `7/7` entries exist, parquet files under directories: `0`
- `retrieval_sources`: `9/9` entries exist, parquet files under directories: `4`
- `code_curriculum_sources`: `4/4` entries exist, parquet files under directories: `96`
- `agent_trace_sources`: `4/4` entries exist, parquet files under directories: `84`
- `locked_eval_sources`: `5/5` entries exist, parquet files under directories: `0`
- `safety_security_sources`: `4/4` entries exist, parquet files under directories: `0`
- `observability_sources`: `3/3` entries exist, parquet files under directories: `0`

## Leakage Controls
- `label_visibility_block` blocks: target_label_visible, label_coded_id, direct_target_field_visible, clean_state_used_as_input
- `source_body_boundary` blocks: raw_source_body_export_requested, body_leak_flag, source_emission_authorized
- `split_contamination` blocks: train_eval_duplicate, source_split_leak, heldout_overlap, locked_eval_source_used_for_training
- `shortcut_proxy_audit` blocks: shortcut_dominated_feature, metadata_only_beats_retrieval, count_proxy_solves_target
- `secret_pii_security` blocks: secret_pattern_present, pii_pattern_present, unknown_license_without_review

## Retrieval Controls
- `retrieval_baseline_card` metrics: bm25_top1_exact, bm25_top5_recall, dense_top1_exact, dense_top5_recall, hybrid_rrf_top5_recall, rerank_top1_exact
- `counterfactual_evidence_card` metrics: evidence_present_accuracy, evidence_removed_drop, wrong_evidence_reject_rate, retrieve_more_rate_on_missing_evidence
- `context_packing_card` metrics: source_span_kept, critical_span_rank_bucket, dropped_evidence_reason_present, context_budget_ok
- `query_expansion_card` metrics: query_variant_count, expansion_source_bits, expansion_lift, expansion_shortcut_baseline

## Locked Eval Controls
- `eval_split_policy`
- `promotion_gate`
- `trace_to_dataset_boundary`
- `benchmark_pack_policy`

## Authority
All model/training/runtime/source/body/Gemma/harness/scoring/promotion authorities remain closed.

## Next Step
Implement Stage8660a/8660b concrete source inventory and shared feature normalizer libraries, then run retrieval and leakage baseline cards on graph/symbol candidate rows.
