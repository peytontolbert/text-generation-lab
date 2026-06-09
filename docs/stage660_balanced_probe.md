# Stage660 Balanced Probe

Summary: `runs/local/artifacts/stage660_balanced_probe_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage660_stage659_balanced_probe_lr1e6_steps80`

Fast eval: `runs/local/artifacts/stage660_stage659_balanced_probe_fast_eval.json`

## Result

- Surface perfect ceiling: `14.223615055503998` KBPP
- Target: `8.0` no-filter answer KBPP
- No-filter exact/answer KBPP: `0.035524560810987996` / `0.3969855535935876`
- No-filter exact/answer accuracy: `0.002156664359124554` / `0.025027956760210874`

## Decision

Rejected as the 8-KBPP rung. Balanced schema exposure alone is not sufficient.

The next algorithmic test should isolate binding capacity: train and evaluate atomic/relation bindings before adding composition, procedures, and counterfactual negatives.
