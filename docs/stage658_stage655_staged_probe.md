# Stage658 Stage655 Staged Probe

Summary: `runs/local/artifacts/stage658_stage655_staged_probe_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage658_stage655_stage3_full_lr1e6_steps40`

Fast eval: `runs/local/artifacts/stage658_stage655_staged_probe_fast_eval.json`

## Result

- Stage sequence: Stage656 bindings -> Stage657 compositions -> Stage658 full
- Target: `8.0` no-filter generalized answer KBPP
- No-filter exact/answer KBPP: `0.03180312576794616` / `0.6104376420456761`
- Delta vs Stage654 answer KBPP: `0.012340618089370481`
- No-filter exact/answer accuracy: `0.0013839829790750035` / `0.029931213980293733`

## Decision

Rejected as the 8-KBPP rung. Accepted as a diagnostic.

The important finding is that selectors alone are not the missing algorithm. The split must be balanced so every field/schema family is trained somewhere; eval should hold out bindings, entities, and compositions rather than entire schema families. Next: `stage659_balanced_generalized_8kbpp_surface`.
