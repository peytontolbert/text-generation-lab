# Stage8630 External Implementation Recovery Inventory

This stage inventories preserved implementation candidates for rebuilding the real 100M AgentKernel Lite software-maintainer model path. It is read-only recovery work: no code is copied, no model is instantiated, no training is run, and all authority gates remain closed.

## Why This Stage Exists

Stage8629 proved that the local `legacy_src/agentkernel_lite/modeling.py` file is only a GRU scaffold. The preserved target is a 102,654,362 parameter transformer/rotary encoder-decoder with agent policy, retrieval, and scalar invariant components. We need to recover implementation sources before touching training.

## Preserved 100M Target

- parameter count: `102654362`
- d_model: `640`
- d_ff: `2048`
- layers: `6`
- heads: `10`
- vocab size: `1506`
- max positions: `4096`
- rope theta: `1000000.0`

## Best Architecture Candidates

- `/data/transformer_10/specs/config.py` | score `25` | lines `59` | arch `6` | trainer `0` | curriculum `1` | missing Stage8580 flags `9`
- `/data/transformer_10/runtime/attention_modules.py` | score `8` | lines `532` | arch `2` | trainer `0` | curriculum `0` | missing Stage8580 flags `9`
- `/data/transformer_10/runtime/block_modules.py` | score `4` | lines `400` | arch `1` | trainer `0` | curriculum `0` | missing Stage8580 flags `9`
- `/data/transformer_10/runtime/attention.py` | score `4` | lines `220` | arch `1` | trainer `0` | curriculum `0` | missing Stage8580 flags `9`
- `/data/transformer_10/runtime/positional.py` | score `4` | lines `511` | arch `1` | trainer `0` | curriculum `0` | missing Stage8580 flags `9`

## Best Trainer Command-Surface Candidates


## Best Curriculum/Compiler Candidates

- `/data/transformer_10/specs/config.py` | score `25` | lines `59` | arch `6` | trainer `0` | curriculum `1` | missing Stage8580 flags `9`
- `/data/agentkernel/scripts/train_agentkernel_lite_encdec.py` | score `14` | lines `2227` | arch `3` | trainer `0` | curriculum `2` | missing Stage8580 flags `9`
- `/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py` | score `10` | lines `4522` | arch `2` | trainer `0` | curriculum `2` | missing Stage8580 flags `9`
- `/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py` | score `10` | lines `3564` | arch `2` | trainer `0` | curriculum `2` | missing Stage8580 flags `9`
- `/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_v202_hybrid_controller_operator_dataset.py` | score `10` | lines `280` | arch `2` | trainer `0` | curriculum `2` | missing Stage8580 flags `9`
- `/data/transformer_10/runtime/seq2seq.py` | score `9` | lines `162` | arch `2` | trainer `0` | curriculum `1` | missing Stage8580 flags `9`
- `/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage51_local_agentkernel_trace_curriculum.py` | score `7` | lines `436` | arch `1` | trainer `0` | curriculum `3` | missing Stage8580 flags `9`
- `/data/transformer_10/scripts/agent_kernel_lite/build_pocketpal_stage52_counterfactual_slot_transform_curriculum.py` | score `7` | lines `356` | arch `1` | trainer `0` | curriculum `3` | missing Stage8580 flags `9`

## Required Recovery Decision

The next stage should inspect the highest-scoring trainer/model candidate in detail and decide whether to adapt it directly or reconstruct a clean `legacy_src/agentkernel_lite/modeling_transformer.py` from the recovered implementation. The safer path is to add a new transformer module and keep the GRU scaffold only for interface tests until shape and parameter-count audits pass.

## Metrics

```json
{
  "architecture_candidates": 5,
  "candidate_paths": 36,
  "curriculum_candidates": 8,
  "readable_candidates": 36,
  "target_d_model": 640,
  "target_heads": 10,
  "target_layers": 6,
  "target_parameter_count": 102654362,
  "target_vocab_size": 1506,
  "trainer_flag_candidates": 0
}
```
