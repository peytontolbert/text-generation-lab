# Stage8622 Central Research Graph

This file records the recovered central graph for the 100M software-maintainer research program. It is a control-plane and documentation artifact only; it does not authorize training, runtime, source/body emission, Gemma, harness, scoring, promotion, or decoder CE.

## Central Spine

1. `100M software maintainer`
2. `structured_policy`
3. `repo_state_graph_v1`
4. `symbol_binding`
5. `edit_localization`
6. `patch_operator`
7. `verifier_repair`
8. `bounded_decoder_arguments`
9. `bounded_decoder_ce_probe`
10. `output_repair_denoise`
11. `controlled_maintainer_loop`
12. `product_harness_integration`

## What The Graph Contains

- `action_label`: 19
- `anti_cheat_rule`: 5
- `architecture_layer`: 11
- `authority_flag`: 10
- `baseline_gate`: 7
- `behavior_value_label`: 14
- `binding_action`: 6
- `build_mode`: 3
- `contract`: 3
- `control_label`: 8
- `counterfactual_obligation`: 21
- `curriculum_route`: 9
- `dataset_judge_signal`: 16
- `derived_field`: 4
- `doc`: 11
- `edit_target`: 7
- `evidence_label`: 5
- `final_objective`: 1
- `fusion_input`: 13
- `fusion_output`: 2
- `gate_feature`: 18
- `graph_family`: 6
- `hard_negative_requirement`: 8
- `loop_phase`: 7
- `loss`: 8
- `manifest_output`: 8
- `mining_must_remain_closed_until`: 10
- `mining_required_card`: 10
- `model_family`: 19
- `model_signal`: 55
- `next_step`: 37
- `objective_family`: 13
- `patch_operator`: 12
- `registry`: 2
- `repo_graph_edge_type`: 18
- `repo_graph_node_type`: 17
- `software_build_action`: 13
- `stage`: 35
- `structured_field`: 22
- `training_blockers_before_mining`: 9
- `verifier_repair_action`: 9

## Recovered Laws

- Learned logits propose; deterministic gates and verifiers authorize.
- Budget safety is deterministic row fact, not learned authority.
- Long outputs stay in holdout unless a separate chunked/long-output curriculum exists.
- Decoder CE only applies to `KEEP_BOUNDED_DECODER` rows with explicit loss masks and cap compliance.
- Mining remains closed until source inventory, judge route, objective family, authority card, loss mask, counterfactuals, shortcut audit, duplicate key audit, split policy, and telemetry contract exist.
- Repo graph IDs, node IDs, and edge IDs must not encode objective labels.

## Artifacts

- `runs/local/artifacts/stage8622_central_research_graph/central_research_graph.json`
- `runs/local/artifacts/stage8622_central_research_graph/central_research_nodes.jsonl`
- `runs/local/artifacts/stage8622_central_research_graph/central_research_edges.jsonl`
- `runs/summaries/stage8622_reconstructed_central_research_graph.json`

## Metrics

```json
{
  "authority_true_reports_seen": 0,
  "curriculum_routes": 9,
  "dataset_judge_signals": 16,
  "docs_attached": 11,
  "edges": 723,
  "gate_features": 18,
  "latest_stage_seen": 8621,
  "mining_families": 8,
  "model_families": 19,
  "nodes": 511,
  "objective_families": 13,
  "stage_summaries_parsed": 37,
  "structured_fields": 22
}
```

## Next Recovery Step

Scrape `/arxiv` targeted long-term storage for ledgers, old session mirrors, preserved checkpoints/manifests, and any research-spine documents, then attach those sources to this graph as recovery-source nodes.
