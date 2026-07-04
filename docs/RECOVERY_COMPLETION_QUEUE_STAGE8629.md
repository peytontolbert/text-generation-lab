# Stage8629 Recovery Completion Queue

This stage centralizes everything still missing after Stage8628. It is a control-plane recovery artifact only. It does not authorize training, runtime, decoder CE, source/body emission, scoring, harness execution, controller merge, or promotion.

## Metrics

```json
{
  "graph_edges": 1470,
  "graph_nodes": 1155,
  "missing_builder_count": 6,
  "missing_builders": [
    "intent_to_build_strategy",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder_arguments",
    "output_repair_denoise"
  ],
  "objectives_with_sources": [
    "intent_to_build_strategy",
    "repo_state_graph_v1_enrichment",
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder_arguments",
    "output_repair_denoise"
  ],
  "partial_builder_count": 2,
  "partial_builders": [
    "repo_state_graph_v1_enrichment",
    "symbol_binding"
  ],
  "queue_items": 8,
  "source_ready_count": 8
}
```

## Recovery Queue

### 1. `intent_to_build_strategy`

- status: `missing_builder`
- matched Stage8628 sources: `7`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `target label hidden from model input`
- `import/repo count baseline <= 0.66`
- `surface/requested-output proxy baseline <= 0.66`
- `authority rows == 0`
- `loss mask excludes decoder_ce`

### 2. `repo_state_graph_v1_enrichment`

- status: `partial_builder_needs_enrichment`
- matched Stage8628 sources: `7`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_partial_or_imbalanced, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `opaque node ids`
- `opaque graph ids`
- `degree profile alone does not solve target`
- `query node id alone does not solve target`
- `authority rows == 0`

### 3. `symbol_binding`

- status: `partial_builder_action_imbalanced`
- matched Stage8628 sources: `7`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_partial_or_imbalanced, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `majority action baseline below 0.45`
- `query kind baseline below 0.66`
- `degree profile baseline below 0.66`
- `no label-coded node ids`

### 4. `edit_localization`

- status: `missing_builder`
- matched Stage8628 sources: `7`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `target path hidden from model input unless visible evidence supports it`
- `filename-only baseline below 0.66`
- `surface proxy baseline below 0.66`
- `authority rows == 0`

### 5. `patch_operator`

- status: `missing_builder`
- matched Stage8628 sources: `5`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `operator label hidden from model input`
- `target span not copied into decoder target unless decoder route later authorized`
- `operator majority baseline below 0.45`
- `authority rows == 0`

### 6. `verifier_repair`

- status: `missing_builder`
- matched Stage8628 sources: `5`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `failure label not copied from target`
- `verifier unavailable routes hold/retrieve`
- `wrong repair action routed negative`
- `authority rows == 0`

### 7. `bounded_decoder_arguments`

- status: `missing_builder`
- matched Stage8628 sources: `4`
- default route: `KEEP_STRUCTURED`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `decoder_budget_ok true for decoder route`
- `raw body/source absent`
- `target token length within cap`
- `loss mask excludes decoder_ce until later explicit authorization`

### 8. `output_repair_denoise`

- status: `missing_builder`
- matched Stage8628 sources: `5`
- default route: `USE_FOR_DENOISE_REPAIR`
- blockers: `builder_missing, needs_source_inventory_card, needs_route_card, needs_loss_mask_card, needs_counterfactual_obligation_card, needs_shortcut_baseline_card, needs_split_overlap_card`

Required gates:

- `bad output present but target hidden`
- `internal leak labels detected`
- `denoise_ce disabled until explicit denoise stage`
- `authority rows == 0`

