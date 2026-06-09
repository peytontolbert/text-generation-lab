# Stage634-635 Rank-2 Residual Bridge

Artifact: `runs/local/artifacts/stage634_635_rank2_residual_bridge_summary.json`

## Summary

Stages634-635 test the residual-selective route identified after Stage632-633. The dataset is built only from train-split Stage626 answer misses with rank `2-4` for the weak families:

- `direct_fact`: `558` replay rows
- `entity_context`: `403` replay rows
- `rule_case_intersection_member`: `311` replay rows

The eval split remains the untouched Stage626 eval.

## Results

| run | exact | answer | exact bits/param | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage626 schema-only frontier | `0.967948717948718` | `0.9794871794871794` | `1.5571586747405581` | `1.5757208311281938` | `75` |
| Stage634 rank-2 bridge | `0.9683760683760684` | `0.9794871794871794` | `1.5578461620141743` | `1.5757208311281938` | `74` |
| Stage635 continued bridge | `0.9683760683760684` | `0.9799145299145299` | `1.5578461620141743` | `1.57640831840181` | `74` |

## Decision

Accepted. Stage635 is the new Stage626-surface neural KBPP frontier.

The important result is that residual-selective training works where whole-surface training failed:

- Stage632/633 whole-surface training tied answer and lost exact.
- Stage634 targeted rank-2/3/4 residual replay gained one exact row.
- Stage635 low-LR continuation kept the exact gain and gained one answer row.

The gain is concentrated in `entity_context`: answer improves from `0.9201388888888888` to `0.9236111111111112`, and exact improves from `0.9166666666666666` to `0.9201388888888888`.

Next route: keep the residual pool narrow. A good follow-up is an `entity_context`-only rank `2-3` bridge or margin-weighted residual replay, while avoiding broad surface replay.
