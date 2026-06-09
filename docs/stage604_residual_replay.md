# Stage604 Residual Replay

Artifact: `runs/local/artifacts/stage604_residual_replay_summary.json`

## Result

Stage604 continued Stage602 for `80` steps on residual replay from Stage602 exact misses plus the Stage602 train mix.

No-filter exact/answer moved from `0.8722222222222222` / `0.8914529914529915` to `0.8713675213675214` / `0.8905982905982905`.

Hard-filter corrections moved from `285` to `287`.

## Decision

`rejected_residual_replay_too_blunt_keep_stage602_best`

## Finding

Naive residual replay from all Stage602 exact misses does not improve the field surface. It lowers no-filter exact/answer and increases hard-filter corrections, mostly by giving back direct_fact margin while leaving entity_context unchanged. Future residual work should filter to answer misses with high rank margin or repair one operation at a time with tighter stopping.
