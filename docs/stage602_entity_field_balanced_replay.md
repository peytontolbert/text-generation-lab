# Stage602 Entity Field Balanced Replay

Artifact: `runs/local/artifacts/stage602_entity_field_balanced_replay_summary.json`

## Result

Stage602 continued Stage601 for `200` steps on the Stage601 field-context schema plus one replay copy of `direct_fact` and `set_intersection_member`.

No-filter exact/answer moved from `0.8662393162393163` / `0.8858974358974359` to `0.8722222222222222` / `0.8914529914529915`.

Hard-filter corrections moved from `299` to `285` with `0` damage.

## Operation Deltas

- `entity_context`: exact/answer `0.5069444444444444` / `0.53125`; exact delta `0.024305555555555525`
- `direct_fact`: exact/answer `0.7476340694006309` / `0.7697160883280757`; exact delta `0.02208201892744477`
- `set_intersection_member`: exact/answer `0.9690721649484536` / `0.9896907216494846`; exact delta `0.005154639175257714`

## Decision

`accepted_as_stage601_entity_field_surface_best`

## Finding

Balanced replay repairs the Stage601 non-target regressions while keeping and extending the field-level entity gain. Direct_fact and set_intersection_member recover above their Stage599-on-Stage601 baselines, entity_context crosses 0.50 exact on the field surface, and hard-filter corrections fall further. This confirms the route: field-level entity context plus balanced replay is a better KBPP schema than whole-card entity replay.
