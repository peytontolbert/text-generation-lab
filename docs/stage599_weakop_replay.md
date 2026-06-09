# Stage599 Weak-Op Replay

Artifact: `runs/local/artifacts/stage599_weakop_replay_summary.json`

## Result

Stage599 continued Stage598 for `300` steps on the weak-op replay dataset with value-anchor weight `0.02` on operation IDs `5,10`.

No-filter exact/answer moved from `0.9008620689655172` / `0.9204980842911877` to `0.9099616858237548` / `0.9300766283524904`.

Hard-filter corrections fell from `201` to `182` with zero damage.

## Weak Ops

- `direct_fact`: exact/answer `0.7413249211356467` / `0.7665615141955836`
- `entity_context`: exact/answer `0.3611111111111111` / `0.3611111111111111`
- `two_hop_owner_region`: exact/answer `0.631578947368421` / `0.6578947368421053`

## Decision

`accepted_as_collision_probe_best_so_far`

## Finding

Weak-op replay plus light value anchoring gives the largest collision-probe gain so far. Most of the gain comes from direct_fact collision recovery; entity_context and two_hop remain largely unresolved, so the next route should either increase collision examples for those families or change their target schema to expose more discriminative anchors.
