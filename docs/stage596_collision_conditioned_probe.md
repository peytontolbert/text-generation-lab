# Stage596 Collision-Conditioned Probe

Artifact: `runs/local/artifacts/stage596_collision_conditioned_probe.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

Rewrote primary retrieval keys for targeted operations so exact-key filtering no longer selects a unique row.

- Train rows rewritten: `8213`
- Eval rows rewritten: `1131`
- Eval target rows: `1131`
- Eval key groups: `903`
- Eval collision rows: `407`
- Eval mean candidate count: `1.2524916943521596`
- Eval max candidate count: `4`

Stage525, without retraining, reaches `0.8836206896551724` exact and `0.9104406130268199` answer without hard filtering.

With strict full-corpus operation-gated hard filtering, Stage525 reaches `0.9971264367816092` exact and `0.9971264367816092` answer. This hard-filter run has `407` multiple-candidate queries and max candidate count `4`.

## Decision

`collision_probe_ready_for_training`

## Finding

The Stage596 probe converts the Stage521/525 curriculum from unique exact-key lookup into collision-conditioned retrieval for the targeted operations. Hard filtering can still narrow by operation/domain-style keys, but the filtered candidate set now contains multiple rows, so value, entity, membership, and composition fields must carry the remaining KBPP.
