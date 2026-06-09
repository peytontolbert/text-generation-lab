# Stage603 Rule Intersection Repair Dataset

Artifact: `runs/local/artifacts/stage603_rule_intersection_repair_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage603_rule_intersection_repair_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target replay ops: `rule_case_intersection_count, rule_case_intersection_member`
- Extra copies per target train row: `1`
- Added train examples: `3870`
- Train examples: `22732` -> `26602`
- Eval examples unchanged: `2340`

## Decision

`rule_intersection_repair_dataset_ready`

## Finding

Stage603 keeps the Stage602 balanced field-context mix and adds one replay copy of rule_case_intersection_count and rule_case_intersection_member to target the remaining small rule-intersection damage.
