# Stage650 Residual Rank Map

Artifact: `runs/local/artifacts/stage650_residual_rank_map.json`

Details: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage650_stage648_continue_lr1e6_steps70/retrieval_eval_stage646_full_corpus_operation_gated_details.jsonl`

## Result

Stage650 residuals are near-rank enough for targeted replay.

- `entity_context`: 188 answer misses; 131 are rank <= 3 and 156 are rank <= 5.
- `two_hop_owner_region`: 34 answer misses; 22 are rank <= 3 and 28 are rank <= 5.
- `rule_case_intersection_count`: 16 answer misses; 15 are rank <= 3.
- `set_intersection_member`: 25 answer misses; 23 are rank <= 3.
- `direct_fact`: already strong at 0.9636 answer; protect it rather than replay broadly.

## Decision

`stage651_residual_targeting_ready`

## Finding

Uniform continuation is mostly saturated, but the remaining failures are often close in rank. The next KBPP gain should target entity_context, two_hop_owner_region, rule_case_intersection_count, and set_intersection_member near misses while protecting direct_fact.
