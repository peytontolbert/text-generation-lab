# Stage600 Entity/Two-Hop Replay Dataset

Artifact: `runs/local/artifacts/stage600_entity_twohop_replay_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage600_entity_twohop_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target ops: `entity_context, two_hop_owner_region`
- Extra copies per target train row: `8`
- Added train examples: `4528`
- Train examples: `16967` -> `21495`
- Eval examples unchanged: `2088`

## Decision

`entity_twohop_replay_dataset_ready`

## Finding

Stage600 isolates the two collision families that did not improve under Stage599 weak-op replay: entity_context and two_hop_owner_region. It heavily oversamples them without changing the Stage596 eval surface.
