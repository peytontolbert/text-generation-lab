# Bounded Decoder CE Candidate Row Recovery Status

The Stage8564-8569 branch is partially recoverable from local session logs.

## Recovered Package Shape

Candidate package design:

- candidate rows: `96`
- languages: `24` each
- splits: `32 / 32 / 32`
- surfaces: `24` each
- copied target text rows: `0`
- over-cap rows: `0`
- current authority rows: `0`

Loss-mask selected rows:

- selected rows: `64`
- train/eval/strict_eval: `32 / 16 / 16`
- languages: `16` each
- surfaces: `16` each
- surfaces: `MAINTAINER_EXPLANATION_ARGS`, `REPAIR_PLAN_ARGS`, `PATCH_HUNK_ARGS`, `TEST_PLAN_ARGS`

Loss contract:

- allowed future loss: `decoder_ce`
- forbidden losses: `structured_aux_ce`, `denoise_ce`, `runtime_reward`, `preference_loss`, `teacher_distill_loss`

## Not Recovered

The actual JSONL row bodies were not recovered from compacted sessions:

- Stage8564 candidate package rows
- Stage8568 loss-mask design rows
- rendered target reference details

## Rule

Do not fabricate decoder CE rows from counts. The counts are enough to rebuild scripts and audits, but not enough to run a real probe.

Next safe step is to rebuild upstream bounded decoder candidate-package scripts or recover original row artifacts from backup/storage, then rerun loss-mask reopen design on real rows.

Artifact: `runs/local/artifacts/stage8591_candidate_row_recovery_status.json`.
