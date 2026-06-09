# Stage650 Stage648 Continuation

Artifact: `runs/local/artifacts/stage650_stage648_continue_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage650_stage648_continue_lr1e6_steps70`

## Result

Stage650 continues Stage648 for 70 more steps, giving 150 effective total steps on Stage646.

- No-filter exact/answer: `0.9057484135871594` / `0.931317655841732`
- No-filter exact/answer bits per param: `3.6926557085953973` / `3.7968992346777313`
- Delta vs Stage648 exact/answer bpp: `0.003043606600944493` / `0.0022827049507077035`
- Hard-filter exact/answer: `0.9985069055617768` / `0.9988801791713325`
- Hard-filter corrections/damage: `497` / `0`

## Decision

`accepted_small_initialized_continuation_gain`

## Finding

Continuing Stage648 for 70 more steps produces a small but real no-filter gain: answer bpp rises from 3.794616529727024 to 3.7968992346777315 and exact bpp rises from 3.689612101994453 to 3.6926557085953975. Hard-filter answer bpp ties Stage648. The weak slices entity_context and two_hop do not move, so the next gain likely needs targeted residual replay or op-specific selectors, not just uniform continuation.
