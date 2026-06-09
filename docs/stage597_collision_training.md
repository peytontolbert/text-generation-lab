# Stage597 Collision Training

Artifact: `runs/local/artifacts/stage597_collision_training_summary.json`

## Result

Stage597 continued Stage525 for `300` steps on the Stage596 collision-conditioned dataset.

No-filter strict full-corpus operation-gated exact/answer moved from `0.8836206896551724` / `0.9104406130268199` to `0.8931992337164751` / `0.914272030651341`.

Hard-filter exact/answer stayed at `0.9971264367816092` / `0.9971264367816092`, but required fewer corrections: `237` -> `217`.

## Decision

`accepted_as_collision_probe_micro_gain`

## Finding

A 300-step 16k continuation on the collision-conditioned dataset produces a small genuine neural gain on the harder no-filter strict eval and reduces the number of deterministic hard-filter corrections needed. The gain is not enough to solve collision-conditioned KBPP, but it confirms Stage596 is a useful non-saturated training surface.
