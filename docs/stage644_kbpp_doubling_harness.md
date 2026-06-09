# Stage644 KBPP Doubling Harness

Artifact: `runs/local/artifacts/stage644_kbpp_doubling_harness.json`

## Result

Stage643 is near the ceiling of its current evaluation surface. It has `1.595657962063062` answer bits/param, but a perfect model on the same surface can only reach `1.6087202202617688` answer bits/param. A true 2x run needs `51954.6232447733` verified answer bits, or `3.191315924126124` answer bits/param at `16280` params.

That requires about `4642` eval rows at the current `11.192292814470767` bits/card density. The current surface has `2340` rows, so the missing ingredient is not another continuation; it is roughly another `2302` independent held-out answer-card choices.

## Entropy Probes

- General KBPP pilot at 256 entities/domain exposes only `5035.740418961495` eval bits, or `0.30932066455537444` perfect bits/param. It is useful as a broad taxonomy, but not dense enough for the 16k doubling gate.
- 64-domain semantic ops generated `4177` eval rows and a perfect ceiling of `3.086118317901473` bits/param. This is close but below the 2x target.
- The 72-domain base surface is materialized at `runs/local/tmp/stage644_semantic_ops_72_domain_seed461_base/agentkernel_lite_encdec_dataset_manifest.json` with `4700` eval rows and `3.521664109018803` perfect bits/param before selector/collision rewrites.

## Next Route

1. Build the `72`-domain semantic-op surface with the Stage626-family compact flags.
2. Apply the proven `domain|field|entity` selector to `direct_fact` and `entity_context`.
3. Recreate collision-conditioned evaluation and balanced replay on the expanded surface.
4. Run a short 16k learnability probe; accept the route only if it clears `1.7552237582693684` answer bits/param before long training.
5. Continue recursive compression only by evidence-gated deletion of redundant selectors.

## Interpretation

The doubling algorithm is now constrained: entropy expansion first, compact identity selectors second, residual-only gradient third, canonicalization last. Anything that only improves Stage643 by a few residual rows cannot materially increase knowledge bits per parameter because the current benchmark is already saturated.
