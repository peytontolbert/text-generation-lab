# Stage8629 Current Model vs Preserved 100M Target Audit

This audit compares the current rebuilt model scaffold against the recovered preserved 100M AgentKernel Lite target config. It is a gap audit only and does not authorize execution or training.

## Result

The current implementation is an interface scaffold, not the recovered 102M target model.

## Supersession Note After Stage8686

Stage8629 remains valid as a historical audit of the old `legacy_src/agentkernel_lite/modeling.py` GRU scaffold. It should not be read as the current recovered transformer status.

Current recovered implementation status from Stage8686:

- `legacy_src/agentkernel_lite/modeling_transformer.py` has `has_rotary=true`
- `legacy_src/agentkernel_lite/modeling_transformer.py` has `has_agent_policy_heads=true`
- `legacy_src/agentkernel_lite/modeling_transformer.py` has `has_retrieval_heads=true`
- `legacy_src/agentkernel_lite/modeling_transformer.py` has `has_scalar_invariant=true`

The remaining control requirement is to block the legacy GRU scaffold from any target 100M training path and require the recovered transformer implementation for target-compatible audits.

## Key Mismatches

- current config uses generic/rebuilt model family, not recovered agentkernel_lite_encdec_v1
- current model implementation is GRU scaffold, not recovered transformer/rotary 100M target
- hidden size mismatch: scaffold 192 vs target d_model 640
- vocab size mismatch: scaffold 259 vs target vocab 1506
- layer count mismatch: scaffold 2 vs target layers 6
- legacy GRU scaffold missing recovered feature: has_rotary
- legacy GRU scaffold missing recovered feature: has_agent_policy_heads
- legacy GRU scaffold missing recovered feature: has_retrieval_heads
- legacy GRU scaffold missing recovered feature: has_scalar_invariant

## Preserved Target

- parameter count: `102654362`
- d_model: `640`
- d_ff: `2048`
- layers: `6`
- heads: `10`
- vocab size: `1506`
- max positions: `4096`
- tokenizer: `agentkernel-bpe`

## Current Scaffold

- GRU scaffold: `True`
- hidden size: `192`
- vocab size: `259`
- layers: `2`

## Required Rebuild Implication

Before real 100M training resumes, require the recovered transformer/rotary AgentKernel Lite implementation and tokenizer compatibility path. The legacy GRU scaffold remains useful for contract tests only and must be blocked for target 100M training.

## Metrics

```json
{
  "current_execution_authorized": false,
  "mismatch_count": 9,
  "scaffold_hidden_size": 192,
  "scaffold_layers": 2,
  "scaffold_uses_gru": true,
  "scaffold_uses_transformer_attention": false,
  "scaffold_vocab_size": 259,
  "target_d_model": 640,
  "target_execution_authorized": false,
  "target_layers": 6,
  "target_parameter_count": 102654362,
  "target_vocab_size": 1506
}
```
