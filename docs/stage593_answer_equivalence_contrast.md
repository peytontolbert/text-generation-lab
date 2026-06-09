# Stage593 Answer-Equivalence Contrast

Artifact: `runs/local/artifacts/stage593_answer_equivalence_contrast_summary.json`

## Result

Stage593 continued Stage525 for `300` steps with answer-level contrastive loss on count/member operation families:

`--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14`

Batch-local exact top1 moved from `0.9952107279693486` to `0.985632183908046`.

Operation-gated exact top1 moved from `0.9966475095785441` to `0.9923371647509579`.

Strict full-corpus operation-gated exact/answer: `0.9746168582375478` / `0.9832375478927203`.

## Decision

`rejected_as_new_best`

## Finding

Answer-equivalence contrast on count/member operation families improves some targeted answer-equivalent slices, but it damages global binding and direct/entity-context retrieval. The loss route is too broad even at weight 0.05; next work should use narrower residual-only examples or deterministic filtering rather than full-dataset answer contrast.
