# Stage8674 Current Gap Review After Retrieval/Eval Controls

The central graph has advanced beyond the first Stage8671 gap review. Stage8671 dense retrieval, Stage8672 locked benchmark packs, and Stage8673 retrieval/eval graph attachment filled two important gaps.

## Filled Now

- Source lineage is ready from Stage8663.
- Shared feature aliases are ready from Stage8664.
- Copy-routed leakage boundary is patched from Stage8669.
- BM25+dense retrieval baseline exists from Stage8671. BM25 remains strongest (`top5=0.998`), dense fallback is usable (`top5=0.983`), hybrid RRF is tracked (`top5=0.994`).
- Locked benchmark packs exist from Stage8672: 5 promotion-only packs, 0 train-eligible packs.
- Retrieval/eval control nodes are attached in Stage8673.

## Still Missing Before Training/Mining

1. Unified `dataset_junk_ood_ranker_v1` central API across all objective families.
2. Cluster, slice, and near-duplicate detector with exact hash, semantic key, MinHash/simhash, split overlap, failure cluster, and undercovered cell output.
3. Cross-encoder reranker card after locked packs are versioned.
4. Source-backed graph/symbol candidate builders that consume Stage8663 lineage, Stage8664 aliases, Stage8669 leakage pass, Stage8671 retrieval, and Stage8672 locked-eval boundaries.
5. Native structured probe telemetry and model-internal interpretability: row loss, field logits, margins, entropy, gradient norms, module deltas, activation/probe cache.
6. Context packing, lost-in-middle ranking, and memory retrieval integration.
7. Dataset cartography and active-learning sampler for scale-up.

## Immediate Next

Stage8675 should build the unified dataset junk/OOD ranker. Stage8676 should build cluster/near-duplicate/slice detection. Only after those pass should source-backed graph/symbol candidate mining resume.

No training, runtime, decoder CE, Gemma, harness, scoring, controller merge, or promotion authority is opened.
