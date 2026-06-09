# Stage651 Rank-3 Residual Replay

Artifact: `runs/local/artifacts/stage651_rank3_residual_summary.json`

Dataset: `runs/local/artifacts/stage651_stage650_rank3_residual_replay_dataset.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage651_stage650_rank3_residual_lr5e7_steps60`

## Result

Stage651 adds `2975` train replay rows selected from Stage650 train answer misses ranked `2-3`, excluding direct_fact.

- No-filter exact/answer: `0.9057484135871594` / `0.9316909294512878`
- No-filter exact/answer bits per param: `3.6926557085953973` / `3.7984210379782035`
- Delta vs Stage650 exact/answer bpp: `0.0` / `0.0015218033004722464`
- Hard-filter exact/answer: `0.9985069055617768` / `0.9988801791713325`
- Hard-filter corrections/damage: `497` / `0`

## Decision

`accepted_tiny_answer_gain_exact_tie`

## Finding

Stage651 targeted rank-2/3 residual replay gives a tiny held-out answer gain while exact ties Stage650. Entity_context answer improves from 0.75 to 0.7526595744680851 and rule_case_intersection_member improves from 0.9416149068322981 to 0.9428571428571428, but rule_case_intersection_count slips from 0.9607843137254902 to 0.9583333333333334. This suggests replay should narrow further to entity_context and maybe two_hop, while removing rule-count from the replay mix.
