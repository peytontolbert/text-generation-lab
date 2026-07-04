# Stage8632 Training Variable Reconciliation

This stage reconciles the central research graph with the recovered 100M transformer implementation. It is a recovery control artifact only and does not authorize training.

## Recovered 100M Model Variables

- `model_family`: `agentkernel_lite_encdec_v1`
- `parameter_count_preserved`: `102654362`
- `parameter_count_estimated_local`: `102599944`
- `d_model`: `640`
- `d_ff`: `2048`
- `n_layers`: `6`
- `n_heads`: `10`
- `vocab_size`: `1506`
- `max_position_embeddings`: `4096`
- `rope_theta`: `1000000.0`
- `retrieval_head_dim`: `128`
- `agent_policy_heads`: `True`
- `agent_intent_labels`: `18`
- `agent_controller_dim`: `128`
- `scalar_invariant_rank`: `32`
- `tokenizer_kind`: `agentkernel-bpe`
- `tokenizer_vocab_size`: `1506`

## Active Objective Chain

`intent_to_build_strategy` -> `repo_state_graph_v1` -> `symbol_binding` -> `edit_localization` -> `patch_operator` -> `verifier_repair` -> `bounded_decoder_arguments` -> `bounded_decoder_ce` -> `output_repair_denoise` -> `controlled_harness_later`

## Still Required Before Training

- `wire transformer implementation behind safe trainer wrapper`: `missing` - local transformer module exists, but trainer execution path still uses contract scaffold and has no authorized model execution
- `bounded decoder CE manifest availability`: `partial` - candidate package was recovered through Stage8580 history, but current rebuild still needs regenerated local rows/loss-mask card before execution
- `agentkernel BPE tokenizer artifact`: `partial` - target tokenizer metadata recovered; concrete tokenizer files must be located or rebuilt from dataset text before full training
- `runtime loss-mask enforcement`: `partial` - safe command surface validates masks in contract-only mode; real loss computation must be connected to row masks before execution
- `telemetry artifacts`: `present_contract_only` - telemetry filenames and stubs exist; real row token loss/logit/module delta artifacts require tiny authorized execution
- `central graph objective coverage`: `present` - central graph lists policy, graph, binding, localization, operator, verifier, bounded decoder, denoise, and promotion families

## Central Graph Coverage

- objective families: `13`
- structured fields: `22`
- model families: `19`
- authority flags: `10`

## Current Best Next Step

Integrate `legacy_src/agentkernel_lite/modeling_transformer.py` behind the safe trainer wrapper as a selectable implementation, then run a non-executing shape/manifest/loss-mask audit. Do not run decoder CE yet.

## Metrics

```json
{
  "authority_flag_nodes": 10,
  "central_graph_kinds": 43,
  "central_graph_nodes": 543,
  "model_family_nodes": 19,
  "objective_family_nodes": 13,
  "recovered_model_variable_count": 17,
  "required_before_training_count": 6,
  "stage8630_passed": true,
  "stage8631_passed": true,
  "structured_field_nodes": 22
}
```
