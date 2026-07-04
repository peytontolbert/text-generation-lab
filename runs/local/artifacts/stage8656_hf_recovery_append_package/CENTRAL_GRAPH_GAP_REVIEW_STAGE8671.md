# Stage8671 Central Graph Gap Review For 100M Maintainer

The current central graph is `stage8670_control_execution_frontier`: **1329 nodes** and **1758 edges**. It has recovered the control spine and names the missing support modules, but several modules are still contract/reference-level rather than reusable training gates.

## Strongly Recovered

- Source lineage: Stage8663 indexes `source_id` / `lineage_hash` and 184 parquet files.
- Shared feature normalization: Stage8664 alias map audited across 4,308 rows.
- BM25 retrieval baseline: top1 `0.8908`, top5 `0.9867`, with strong lift over metadata and evidence-removed controls.
- Leakage boundary: Stage8665 found `visible_target_hits:360`; Stage8669 fixed it to `0` with copy-routed intent rows.
- Storage/safety: Stage8653 focused storage and single safe cleanup contract are active.

## Still Missing Or Partial

- Unified `dataset_junk_ood_ranker_v1`: script pieces exist, but no central API yet scores every row across structured, decoder, denoise, long-output, retrieval, and graph objectives.
- Cluster/slice/near-duplicate detector: support registry names it, but no current stage emits `cluster_id`, `failure_cluster`, `slice_gap`, `near_duplicate_cluster`, or MinHash/simhash split-overlap cards.
- Dense retrieval/reranker/hybrid fusion: BM25 baseline exists; dense + cross-encoder + fusion card is still next.
- Locked benchmark/eval pack: policy exists; materialized immutable eval packs and train-exclusion checks need reusable builders.
- Training interpretability: telemetry contracts exist, but current maintainer native probes still need row loss, per-field logits, margin/entropy, gradient norms, module deltas, and activation/probe caches.
- Context packing and memory: modules are named, but not wired into candidate builders or curriculum rows.

## Next Fill Order

1. Stage8672 unified dataset junk/OOD ranker.
2. Stage8673 cluster, near-duplicate, and slice-gap detector.
3. Stage8674 dense retrieval + cross-encoder rerank + hybrid fusion against Stage8666 BM25.
4. Stage8675 locked benchmark pack materialization and source-id exclusion audit.
5. Stage8676 source-backed graph/symbol candidate builders using Stage8663 lineage, Stage8664 aliases, Stage8666 retrieval, and Stage8669 copy-route leakage boundary.
6. Stage8677 native structured probe telemetry/interpretability design.

No training, runtime, decoder CE, Gemma, harness, scoring, controller merge, or promotion authority is opened by this review.
