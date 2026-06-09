# Stage649 Scratch Control

Artifact: `runs/local/artifacts/stage649_scratch_control_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage649_stage646_scratch_probe_lr1e6_steps80`

## Result

Stage649 tests whether Stage646 is learnable from random initialization in the same 80-step budget. It is not.

- No-filter exact/answer: `0.004292646509891751` / `0.3624486748786861`
- No-filter exact/answer bits per param: `0.017500737955428426` / `1.4776710047583475`
- Hard-filter exact/answer: `0.9766703994027622` / `0.9822695035460993`
- Hard-filter answer bits/param: `4.004625385192164`
- Hard-filter corrections: `5210`
- Hard-filter masked neural top1s: `5329`

## Decision

`rejected_as_pure_neural_2x_control_but_confirms_hard_filter_ceiling`

## Finding

A random-init 16k model does not learn the Stage646 surface in 80 steps: no-filter exact bpp is only 0.017500737955428426 and answer bpp is 1.4776710047583475. Hard filtering recovers 4.004625385192165 answer bpp, but with 5210 corrections and 5329 masked neural top1s, so this is an access-layer result rather than learned KBPP. The 2x pure-neural result requires prior tiny retrieval geometry plus the entropy-expanded selector surface.
