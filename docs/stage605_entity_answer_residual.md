# Stage605 Entity Answer Residual

Artifact: `runs/local/artifacts/stage605_entity_answer_residual_summary.json`

## Result

Stage605 continued Stage602 for `100` steps on only `entity_context` answer misses plus entity near-misses.

No-filter exact/answer moved from `0.8722222222222222` / `0.8914529914529915` to `0.8726495726495727` / `0.8910256410256411`.

Hard-filter corrections moved from `285` to `284`.

- `entity_context`: exact/answer `0.5069444444444444` / `0.53125`; exact delta `0.0`
- `direct_fact`: exact/answer `0.7444794952681388` / `0.7665615141955836`; exact delta `-0.003154574132492094`
- `set_intersection_member`: exact/answer `0.979381443298969` / `0.9896907216494846`; exact delta `0.010309278350515427`

## Decision

`exact_micro_gain_but_answer_tradeoff_keep_stage602_balanced_best`

## Finding

Filtering residual replay to entity_context answer misses is much less damaging than Stage604 and yields a one-row exact gain plus one fewer hard-filter correction. However, entity_context top1 does not improve, answer top1 drops by one row, and direct_fact slips. Stage605 is useful evidence that filtered residuals are safer, but Stage602 remains the balanced best checkpoint.
