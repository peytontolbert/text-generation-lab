# Stage599 Collision Weak-Op Replay Dataset

Artifact: `runs/local/artifacts/stage599_collision_weakop_replay_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage599_collision_weakop_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Weak ops: `direct_fact, entity_context, two_hop_owner_region`
- Extra copies per weak-op train row: `2`
- Added train examples: `5618`
- Train examples: `16967` -> `22585`
- Eval examples unchanged: `2088`

## Decision

`weakop_replay_dataset_ready`

## Finding

Stage599 weak-op replay oversamples direct_fact, entity_context, and two_hop_owner_region on the collision-conditioned training set while keeping the Stage596 eval unchanged. This targets the collision families that remained weakest after Stage598.
