# Stage638 Fresh Entity Rank-3 Bridge

Artifact: `runs/local/artifacts/stage638_fresh_entity_rank3_bridge_summary.json`

## Summary

Stage638 retests the Stage636 entity replay route using fresh Stage636 train residuals instead of stale Stage626 residuals.

The refreshed train residual pass found `332` `entity_context` answer misses where the correct card was ranked `2-3`:

- rank `2`: `242`
- rank `3`: `90`

Stage638 trained a corrected 40-step MoE continuation from Stage636 at `2e-7` learning rate. A first launch produced a dry-run control artifact without the Stage636 architecture; that artifact is not used for the decision.

## Results

| run | exact | answer | exact bits/param | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage636 frontier | `0.9692307692307692` | `0.9803418803418803` | `1.5592211365614065` | `1.5770958056754263` | `72` |
| Stage638 fresh entity bridge | `0.9688034188034188` | `0.9803418803418803` | `1.5585336492877905` | `1.5770958056754263` | `73` |

## Decision

Rejected as a frontier. Stage636 remains the accepted Stage626-surface neural KBPP frontier.

Stage638 ties answer but loses one exact row and needs one more hard-filter correction. The lost exact row is in `set_intersection_member`, while `entity_context` itself stays unchanged at `0.9236111111111112` exact and `0.9270833333333334` answer.

## Updated Rule

Entity-only residual replay has reached its useful early-stop point. The next KBPP work should not spend more gradient on the same entity residual pool.

The fresh train residual map shows large rank `2-3` pools outside entity-context, but they need different treatment:

- `direct_fact`: `496` answer rank `2-3` train misses, but prior mixed direct replay did not move held-out direct-fact accuracy.
- `rule_case_intersection_member`: `279` answer rank `2-3` train misses, but held-out misses include many exact-card swaps.
- `set_intersection_member`: `138` answer rank `2-3` train misses, but Stage638 already shows this slice is easy to damage with unrelated replay.

Next branch: direct-fact residual geometry, then schema-level direct-value disambiguation if the miss pattern is mostly same-domain/same-field entity binding rather than missing exposure.
