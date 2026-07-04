# Stage8676 Central Graph Gap Review

Current registry frontier: `stage8675_source_backed_symbol_binding_candidate_manifest_audit`.

Stage8675 failed correctly. The source-backed symbol-binding candidate manifest is lineage-controlled, leak-clean, authority-closed, and balanced by action, but one shortcut cell remains:

- feature: `query_kind`
- value: `test`
- majority action: `BIND_TEST_TO_SYMBOL`
- majority exact: `0.8621`
- cell rows: `29`

This means source-backed symbol binding is not yet model-ready. The next repair should add counterbalanced `query_kind=test` rows where the correct action is not only `BIND_TEST_TO_SYMBOL`, especially:

- `test -> RETRIEVE_MORE`
- `test -> ABSTAIN_UNBOUND`
- `test -> BIND_FAILURE_TO_SYMBOL`
- `test -> BIND_CALL_TO_SYMBOL`

## Filled Since Stage8674

- Source inventory lineage exists and is used by candidate manifests.
- Shared feature normalizer exists and is audited.
- Retrieval controls exist: BM25, dense fallback, and hybrid RRF baselines.
- Locked benchmark packs exist as promotion-only packs.
- Copy-routed leakage repair removed visible target hits in patched intent/build rows.
- Source-backed symbol-binding candidate builder exists.
- Source-backed symbol-binding audit exists and blocks shortcut-dominated cells.

## Still Missing Before Training/Mining

1. `dataset_junk_ood_ranker_v1`
   - Current ranker signals exist, but not as one central API over all objective families.
   - Must emit row route, risk bucket, junk/OOD reason bits, and loss eligibility.

2. Cluster / slice / near-duplicate detector
   - Need exact hash, semantic key, MinHash/simhash, failure cluster, split overlap, and undercovered-cell reports.
   - Must run before scaling source-backed graph rows.

3. Source-backed symbol-binding shortcut repair
   - Stage8675 proves `query_kind=test` still predicts the target too strongly.
   - Need counterbalanced test-query rows and rerun the audit.

4. Cross-encoder reranker / rerank calibration
   - Stage8671 recovered retrieval baselines, but no learned or cross-encoder rerank card is active.
   - Reranker confidence must never authorize decode by itself.

5. Native probe telemetry and internal interpretability
   - Still missing row-level logits, margins, entropy, losses, gradient norms, module deltas, activation caches, and failure buckets for native structured probes.

6. Context packing and lost-in-middle controls
   - Context packer and memory retrieval evaluator are named in the graph, but not implemented as cards.

7. Dataset cartography / active learning sampler
   - Need confidence/variability/forgetting-style row buckets before scaling.

8. Reusable locked-eval exclusion in every builder
   - Stage8672 has locked packs; future builders must reject locked source IDs automatically.

## Current Safe Next Sequence

1. Stage8676: write this current gap review.
2. Stage8677: patch source-backed symbol-binding with counterbalanced `query_kind=test` rows.
3. Stage8678: rerun source-backed symbol-binding audit.
4. Stage8679: build unified `dataset_junk_ood_ranker_v1`.
5. Stage8680: build cluster / near-duplicate / slice detector.
6. Stage8681: attach these to the central graph.

No training, decoder CE, runtime, Gemma, harness, source/body emission, or promotion authority is opened.
