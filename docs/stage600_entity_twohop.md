# Stage600 Entity/Two-Hop Replay

Artifact: `runs/local/artifacts/stage600_entity_twohop_summary.json`

## Result

Stage600 continued Stage599 for `300` steps on heavy `entity_context`/`two_hop_owner_region` replay with value-anchor weight `0.1`.

Global no-filter exact/answer moved from `0.9099616858237548` / `0.9300766283524904` to `0.9094827586206896` / `0.9315134099616859`.

Hard-filter corrections moved from `182` to `183`.

## Target Ops

- `entity_context`: exact/answer `0.3333333333333333` / `0.3333333333333333`; exact delta `-0.02777777777777779`
- `two_hop_owner_region`: exact/answer `0.7105263157894737` / `0.7368421052631579`; exact delta `0.07894736842105265`

## Decision

`rejected_as_new_collision_frontier_but_twohop_positive`

## Finding

Entity/two-hop replay with stronger value anchoring is mixed. It improves two-hop collision resolution materially, but global exact drops slightly, hard-filter corrections rise by one, and entity_context regresses. This suggests two-hop benefits from more exposure, while entity_context needs a schema redesign rather than heavier replay.
