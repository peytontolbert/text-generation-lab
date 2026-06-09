# Stage632-633 Selector Surface Training

Artifact: `runs/local/artifacts/stage632_633_selector_surface_training_summary.json`

## Summary

Stages632-633 test whether the Stage626 schema-only frontier can be converted into more neural KBPP through retrieval-only continuation.

- Stage632 trains directly on the Stage626 accumulated selector surface.
- Stage633 trains on a 1:1 interleaved bridge mix of Stage626 accumulated rows and Stage628 canonical rows.

## Results On Stage626 Eval

| run | exact | answer | exact bits/param | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage626 schema-only frontier | `0.967948717948718` | `0.9794871794871794` | `1.5571586747405581` | `1.5757208311281938` | `75` |
| Stage632 direct Stage626 training | `0.9675213675213675` | `0.9794871794871794` | `1.5564711874669422` | `1.5757208311281938` | `76` |
| Stage633 bridge mix training | `0.9675213675213675` | `0.9794871794871794` | `1.5564711874669422` | `1.5757208311281938` | `76` |

Stage633 on the Stage628 canonical eval reaches exact/answer `0.9534188034188035` / `0.9666666666666667`, tying the Stage630 answer but not Stage631.

## Decision

Rejected as a frontier. Generic continuation over selector surfaces does not expand Stage626 KBPP. It preserves answer but loses one exact row and needs one more hard-filter correction.

The new constraint is sharper: the remaining recoverable bits are not in whole-surface exposure. They are in targeted rank-2 residuals, especially `entity_context` and `direct_fact`, where the model already nearly ties the correct card but chooses a near neighbor. The next attempt should build targeted residual bridge rows from Stage626 miss details rather than duplicating complete surfaces.

Follow-up: Stage634-635 validates this route. See `docs/stage634_635_rank2_residual_bridge.md`.
