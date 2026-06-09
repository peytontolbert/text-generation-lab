# Stage636-637 Entity Rank-3 Bridge

Artifact: `runs/local/artifacts/stage636_637_entity_rank3_bridge_summary.json`

## Summary

Stages636-637 test the follow-up from Stage634-635: keep the residual bridge narrow and focus only on the family that actually moved.

Stage636 builds an `entity_context`-only replay set from train-split Stage626 answer misses where the correct card was already near the top:

- rank `2`: `258` replay rows
- rank `3`: `96` replay rows
- total replay rows: `354`

The eval split remains the untouched Stage626 eval.

## Results

| run | exact | answer | exact bits/param | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage635 rank-2 bridge | `0.9683760683760684` | `0.9799145299145299` | `1.5578461620141743` | `1.57640831840181` | `74` |
| Stage636 entity rank-3 bridge | `0.9692307692307692` | `0.9803418803418803` | `1.5592211365614065` | `1.5770958056754263` | `72` |
| Stage637 continued bridge | `0.9683760683760684` | `0.9803418803418803` | `1.5578461620141743` | `1.5770958056754263` | `74` |

## Decision

Accepted Stage636. Rejected Stage637 as over-continuation.

Stage636 is the new Stage626-surface neural KBPP frontier. It improves both exact and answer density, raises `entity_context` exact/answer to `0.9236111111111112` / `0.9270833333333334`, and reduces hard-filter corrections from `74` to `72`.

Stage637 preserves the answer gain but gives back the exact gain and needs two more hard-filter corrections. That makes Stage636 the early-stop point.

## Current Residual Map

A fresh Stage636 detail pass leaves these answer-miss rank `2-3` pools on the Stage626 eval split:

| operation | exact misses | answer misses | rank 2-3 answer misses |
| --- | ---: | ---: | ---: |
| `entity_context` | `22` | `21` | `21` |
| `direct_fact` | `13` | `13` | `13` |
| `rule_case_intersection_member` | `28` | `9` | `9` |
| `set_intersection_member` | `4` | `2` | `2` |
| `rule_case_intersection_count` | `3` | `1` | `1` |

This keeps `entity_context` as the main residual pool, but it also shows why the next replay should not simply repeat Stage634: `direct_fact` remains unchanged after mixed and entity-only bridge training, so it needs a diagnostic or schema change before more exposure.

## Next Step

Build the next residual scheduler from Stage636 details, not from stale Stage626/635 residuals. The candidate pool should be operation-local and rank-limited:

- keep `entity_context` rank `2-3` residuals, but use a smaller step budget with checkpoint selection;
- diagnose `direct_fact` before replaying it again, because Stage634-637 left direct-fact unchanged;
- keep `rule_case_intersection_member` out unless the new Stage636 detail pass shows fresh near misses that are answer-positive rather than exact-card swaps.
