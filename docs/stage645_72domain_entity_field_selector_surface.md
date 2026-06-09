# Stage645 72-Domain Entity Field Selector Surface

Artifact: `runs/local/artifacts/stage645_72domain_entity_field_selector_surface_dataset.json`

Dataset manifest: `runs/local/tmp/stage645_72domain_entity_field_selector_surface/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Train rows: `34468` -> `38850`
- Eval rows: `4700` -> `5358`
- Direct-fact selector rows: train `5074`, eval `686`
- Entity-context rows: train `626` -> `5008`, eval `94` -> `752`
- Eval entity field collision rows: `568`
- Eval entity field mean/max candidate count: `1.8431372549019607` / `4`
- Perfect answer ceiling: `4.076911041964586` bits/param at `16280` params

## Decision

`stage645_selector_surface_ready_for_collision_eval`

## Finding

Stage644's whole-entity entity_context rows cannot use the Stage643 domain|field|entity selector directly. Stage645 first factors entity_context into field-level answer rows, then applies the same compact selector to direct_fact and entity_context on the 72-domain entropy-expanded surface.
