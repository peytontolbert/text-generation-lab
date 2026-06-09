# Stage648 Stage525-Init Control

Artifact: `runs/local/artifacts/stage648_stage525init_control_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage648_stage646_stage525init_probe_lr1e6_steps80`

## Result

Stage648 tests whether Stage647 needed the Stage636 selector-trained checkpoint. It does not: the older Stage525 checkpoint also clears the 2x answer-KBPP gate on Stage646.

- Source Stage643 answer bits/param: `1.595657962063062`
- 2x target: `3.191315924126124`
- Stage648 no-filter answer bits/param: `3.7946165297270236`
- Multiple vs Stage643: `2.378088926288989`
- No-filter exact/answer: `0.9050018663680478` / `0.9307577454273983`
- Delta vs Stage647 answer bpp: `0.006848114852123999`
- Hard-filter exact/answer: `0.9985069055617768` / `0.9988801791713325`
- Hard-filter corrections/damage: `501` / `0`

## Decision

`accepted_control_reproduces_2x_kbpp_from_stage525_init`

## Finding

Stage648 reproduces the 2x answer-KBPP result from the older Stage525 checkpoint. No-filter answer bits/param reaches 3.794616529727024, slightly above Stage647, while exact bits/param is slightly lower. This indicates the Stage646 entropy-expanded collision-conditioned selector surface is the main driver; Stage636 initialization is not required for the 2x answer result.
