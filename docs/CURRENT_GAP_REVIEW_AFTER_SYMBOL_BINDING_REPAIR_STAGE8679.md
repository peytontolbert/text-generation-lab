# Stage8679 Current Gap Review After Symbol-Binding Repair

Current frontier: `stage8678_symbol_binding_repair_graph_attachment`.

The central graph now has:

- graph nodes: `1337`
- graph edges: `1777`
- latest validated source-backed candidate stage: `8677`
- all authority counts: `0`

## What Is Back In Place

The recovered pipeline now has the important control pieces required before mining or training:

- focused storage policy and single cleanup contract
- stage registry
- central research graph
- source inventory lineage registry
- shared feature normalizer
- leakage and locked-eval boundary cards
- BM25 / dense fallback / hybrid retrieval baseline
- locked benchmark pack manifest
- copy-routed leakage repair
- intent/build, edit localization, patch operator, verifier repair, bounded argument objectives
- 100M model target config and tokenizer pointer
- structured trainer/probe scaffold
- source-backed symbol-binding candidate builder
- source-backed symbol-binding shortcut repair
- graph attachment for the symbol-binding repair chain

## Current Source-Backed Symbol Binding Status

Stage8674 built 125 source-backed rows, balanced 25 per action:

- `RETRIEVE_MORE`
- `BIND_CALL_TO_SYMBOL`
- `BIND_TEST_TO_SYMBOL`
- `ABSTAIN_UNBOUND`
- `BIND_IMPORT_TO_MODULE`

Stage8675 correctly failed due one shortcut:

- `query_kind=test` predicted `BIND_TEST_TO_SYMBOL` at `0.8621`

Stage8676 repaired this by down-capping to 80 rows, 16 per action, preserving the available test-query counterexamples:

- `query_kind=test`: 20 rows
- `BIND_TEST_TO_SYMBOL`: 16
- `RETRIEVE_MORE`: 4
- majority: `0.8`

Stage8677 passed the repaired audit:

- missing controls: `0`
- visible target hits: `0`
- forbidden authority/loss rows: `0`
- shortcut feature cells: `0`

Stage8678 attached the repair chain to the central graph.

This is good enough as a candidate-only source-backed symbol-binding seed, but not enough to scale or train.

## Most Important Remaining Gaps

1. More test-query counterexamples
   - `query_kind=test` is only barely under the shortcut ceiling.
   - Need more `test -> RETRIEVE_MORE`, `test -> ABSTAIN_UNBOUND`, and if valid, `test -> BIND_FAILURE_TO_SYMBOL` / `test -> BIND_CALL_TO_SYMBOL` style rows.
   - Do not increase row count until this is counterbalanced.

2. Unified `dataset_junk_ood_ranker_v1`
   - The graph contains many judge/ranker signals, but they are still scattered.
   - Need one central API that emits:
     - `junk_score`
     - `ood_score`
     - `risk_bucket`
     - `route`
     - reason bits
     - loss eligibility
     - train/eval/holdout eligibility

3. Cluster / slice / near-duplicate detector
   - Need exact hash, semantic key, MinHash/simhash, source lineage cluster, failure cluster, split overlap, and undercovered-cell cards.
   - This must run before mining from `/arxiv/datasets` or `/arxiv/repositories`.

4. Cross-encoder reranker and calibration
   - Retrieval baselines exist, but no cross-encoder rerank card is active.
   - Reranker confidence should improve evidence ordering, not authorize decoding.

5. Training telemetry and internal interpretability
   - The trainer scaffold exists, but native probes still need full telemetry:
     - row field logits
     - margins / entropy / confidence
     - row losses
     - token losses for decoder probes
     - gradient norms
     - module delta norms
     - activation/probe cache
     - failure bucket cards

6. Context packing / lost-in-middle / memory retrieval
   - Named in the central graph and support module indices.
   - Not yet executable as cards.
   - Needed before repo-wide context packets become large.

7. Dataset cartography and active-learning sampler
   - Need row difficulty, ambiguity, confidence variance, forgetting, and high-value residual selection.
   - This should guide scale-up instead of random mining.

8. Reusable locked-eval exclusion in every builder
   - Locked packs exist, but builders need a shared guard that rejects locked source IDs automatically.

9. Loss-mask enforcement across all objectives
   - Current manifests carry loss masks, but the compiler needs a single loss-mask card per manifest.
   - Every row must declare exactly which losses may create gradients.

10. Source-backed expansion beyond symbol binding
   - Symbol binding now has a repaired seed.
   - Edit localization, patch operator, verifier repair, and bounded arguments still need source-backed versions with the same lineage/retrieval/leakage/shortcut controls.

## State-Space Coverage Checklist

Recovered or partially recovered:

- intent/build strategy
- repo graph substrate
- source lineage
- shared normalized features
- symbol binding seed
- edit localization objective
- patch operator objective
- verifier repair objective
- bounded decoder argument objective
- bounded decoder CE candidate package
- output repair denoise objective
- junk/risk signals
- shortcut baselines
- leakage controls
- locked-eval controls
- retrieval baseline
- focused storage and cleanup safety

Still missing as executable central modules:

- unified junk/OOD ranker
- cluster/slice/near-duplicate detector
- cross-encoder reranker
- context packer
- lost-in-middle ranker
- memory retrieval evaluator
- dataset cartography sampler
- active learning residual miner
- gradient/activation telemetry
- module delta audit
- confidence calibration card
- source-backed edit/localize/operator/repair builders

## Safe Next Sequence

1. Stage8680: mine or construct additional `query_kind=test` counterexamples.
2. Stage8681: rerun source-backed symbol-binding shortcut audit at larger count.
3. Stage8682: build unified `dataset_junk_ood_ranker_v1`.
4. Stage8683: build cluster / near-duplicate / slice detector.
5. Stage8684: attach ranker and cluster detector to the central graph.
6. Stage8685: build source-backed edit-localization candidate manifest.

Training and mining remain closed until the ranker and cluster/slice detectors pass.
