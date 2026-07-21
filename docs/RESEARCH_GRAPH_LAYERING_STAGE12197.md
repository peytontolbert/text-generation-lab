# Research Graph Layering Stage12197

Stage12197 resolves a compression concern: the central graph is a control spine, not the full 12k-stage memory.

## Finding

The integrated graph with Stage12196 had `556` nodes and `777` edges, while the workspace has `3,125` stage summaries from Stage8587 through Stage12196.

That compression is acceptable only if the graph is treated as current authority:

- selected frontiers,
- blockers,
- gates,
- claim boundaries,
- next stage plans.

It is not acceptable as the only memory of prior experiments.

## Layering Decision

Use layers:

1. Control spine
   Current selected state, blockers, gates, bans, and next plans.

2. Evidence cluster ledger
   Rollups for repeated experiment families and failure mechanisms.

3. Raw stage index
   One record per summary, used for query and traceability.

4. Future ledgers
   Frontier ledger, failure mechanism ledger, dataset/source ledger, and trainer capability ledger should be added as append-only JSONL layers.

## Stage12197 Outputs

- `runs/local/artifacts/stage12197_graph_coverage_audit/raw_stage_index.jsonl`
- `runs/local/artifacts/stage12197_graph_coverage_audit/evidence_cluster_ledger.jsonl`
- `runs/local/artifacts/stage12195_central_graph_integration/central_research_graph_with_stage12197_evidence_layers.json`
- `runs/summaries/stage12197_graph_coverage_audit.json`

## Evidence Clusters Added

- `language_source_supply_lineage`
- `transition_candidate_next_action_tradeoff`
- `selected_test_same_shape_regression`
- `suffix_residual_denoise_lessons`
- `v27_hardened_weighted_blended_lineage`
- `closed_loop_episode_supply`
- `tokenizer_diagnostic_lane`
- `gemma_comparison_claims`

## Rule

Training decisions should consume:

- control spine for current authority,
- frontier ledger for improvement baselines,
- dataset/source ledger for admissibility,
- trainer capability ledger for executable safety,
- failure ledger for known traps.

Raw summaries are evidence, not authority.
