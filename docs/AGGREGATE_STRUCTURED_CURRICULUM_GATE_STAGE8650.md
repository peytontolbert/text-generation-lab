# Stage8650 Aggregate Structured Curriculum Gate

This is a no-authority aggregate gate over the recovered structured objectives. It does not authorize training, decoder CE, denoise CE, runtime, source/body emission, harness execution, Gemma, scoring, or promotion.

## Objective Status
- `intent_to_build_strategy`: passed=True, rows=360, max_proxy=0.200
- `edit_localization`: passed=True, rows=504, max_proxy=0.143
- `patch_operator`: passed=True, rows=864, max_proxy=0.083
- `verifier_repair`: passed=True, rows=648, max_proxy=0.111
- `bounded_decoder_arguments`: passed=True, rows=504, max_proxy=0.429
- `output_repair_denoise`: passed=True, rows=360, max_proxy=0.208

## Hard Blockers Before Training
- repo_state_graph_v1 enrichment remains source-sparse/synthetic-small
- symbol_binding remains partial and imbalance-prone
- source-backed expansion and junk/ranker gates are not yet attached to the recovered objectives
- native model/training/decode/runtime authority is still intentionally closed

## Next Step
Repair symbol_binding and repo_state_graph_v1 enrichment, then attach source-backed reservoir sampling plus junk/ranker gates before any training candidate.
