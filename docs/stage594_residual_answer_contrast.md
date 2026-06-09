# Stage594 Residual Answer-Equivalence Contrast

Artifact: `runs/local/artifacts/stage594_residual_answer_contrast_summary.json`

## Result

Stage594 continued Stage525 for `80` steps on only the operation-gated residual set: `140` residual examples from `7` misses plus `7` near-miss eval source ids.

Training kept answer-level contrastive loss on count/member operation families:

`--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14`

Against a refreshed current-evaluator Stage525 baseline, batch-local exact/answer moved from `0.9894636015325671` / `0.9932950191570882` to `0.9904214559386973` / `0.9937739463601533`.

Against the same refreshed baseline, operation-gated exact/answer moved from `0.992816091954023` / `0.9956896551724138` to `0.9937739463601533` / `0.9966475095785441`.

Strict full-corpus operation-gated exact/answer: `0.9755747126436781` / `0.9846743295019157`.

The established historical Stage525 raw-density artifact remains higher: exact/answer `0.9952107279693486` / `0.9971264367816092`, bits/param `1.410325570323004`.

## Decision

`current_evaluator_micro_gain_not_new_historical_frontier`

## Finding

Residual-only answer-equivalence contrast is less destructive than broad Stage593 and gives a tiny current-evaluator gain over a refreshed Stage525 baseline. The gain is only one to two eval rows, and it still does not supersede the established historical Stage525 raw-density frontier. Treat this as evidence that residual-only contrast can polish specific residuals, not as a robust KBPP lever. The next lever should be deterministic answer-equivalent filtering, eval-time structured correction, or higher-entropy target schemas.
