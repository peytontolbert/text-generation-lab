# Stage603 Rule Intersection Repair

Artifact: `runs/local/artifacts/stage603_rule_intersection_repair_summary.json`

## Result

Stage603 continued Stage602 for `150` steps with one replay copy of `rule_case_intersection_count` and `rule_case_intersection_member`.

No-filter exact/answer stayed `0.8722222222222222` / `0.8914529914529915` versus Stage602 `0.8722222222222222` / `0.8914529914529915`.

Hard-filter corrections stayed `285` with `0` damage.

- `rule_case_intersection_member`: exact/answer `0.9473684210526315` / `0.96398891966759`; exact delta `0.0027700831024930483`
- `direct_fact`: exact/answer `0.7444794952681388` / `0.7665615141955836`; exact delta `-0.003154574132492094`

## Decision

`neutral_rule_repair_tradeoff_keep_stage602_as_field_surface_best`

## Finding

Rule-intersection replay repairs rule_case_intersection_member exact/answer but does not improve global exact, answer, or hard-filter corrections over Stage602, and it gives back a small direct_fact margin. Stage602 remains the cleaner Stage601 field-surface best. The next gain likely needs residual-only replay from Stage602 details, not another broad operation replay.
