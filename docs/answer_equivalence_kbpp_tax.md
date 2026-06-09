# Answer-Equivalence KBPP Tax

Artifact: `runs/local/artifacts/answer_equivalence_kbpp_tax.json`

## Finding

The evaluator already separates exact-card retrieval from answer-equivalent retrieval. The remaining maximization question is where exact proof-card identity consumes KBPP without adding answer knowledge.

Largest observed gap:

- Operation: `rule_case_intersection_count`
- Run: `knowledge_compression_moe_residual_10k_stage579_stage525_compact_membership_cards_lr1e4_steps300`
- Answer bits/param: `0.12531711359738507`
- Exact bits/param: `0.12193016458123951`
- Gap: `0.0033869490161455573`

## Ranked Tax By Operation

- `rule_case_intersection_count`: max bits/param tax `0.0033869490161455573`, top1 tax `0.027027027027026973`, example `knowledge_compression_moe_residual_10k_stage579_stage525_compact_membership_cards_lr1e4_steps300`
- `set_intersection_member`: max bits/param tax `0.00203216940968734`, top1 tax `0.015463917525773141`, example `stage502_16k_compact_false_claim_2100step`
- `rule_default`: max bits/param tax `0.0006773898032291087`, top1 tax `0.016949152542372836`, example `stage501_16k_compact_false_claim_1500step`
- `set_count`: max bits/param tax `0.0006773898032291087`, top1 tax `0.005464480874316946`, example `stage500_16k_compact_false_claim_900step`
- `set_intersection_count`: max bits/param tax `0.0006773898032291087`, top1 tax `0.0092592592592593`, example `knowledge_compression_moe_residual_10k_stage579_stage525_compact_membership_cards_lr1e4_steps300`
- `set_member`: max bits/param tax `0.0006773898032290948`, top1 tax `0.0028901734104046506`, example `stage474_16k_continued_compact_reverse_comp_key`
- `rule_case_intersection_member`: max bits/param tax `0.0005264922179208376`, top1 tax `0.0027700831024930483`, example `stage510_21k_d10_compact_false_claim_900step`

## Training Route

Use answer-level contrastive pressure on set/rule count and membership operations:

`--retrieval-answer-contrastive-weight 0.05 --retrieval-answer-contrastive-operation-ids 6,7,8,9,11,12,13,14`

This targets operations `6,7,8,9,11,12,13,14`: set/rule count and membership families. The goal is to reward the useful answer knowledge, such as counts and `member_true/member_false`, while reducing pressure to memorize arbitrary exact proof-card identity.

## Stage593 Check

Stage593 tested this route from Stage525 with low learning rate and weight `0.05`. It is rejected as a new best: batch-local exact fell from `0.9952107279693486` to `0.985632183908046`, and strict full-corpus operation-gated exact/answer was `0.9746168582375478` / `0.9832375478927203`.

The useful lesson is narrower: answer-level contrast can fix selected answer-equivalent slices, but full-dataset application still steals global binding geometry. The next version should use residual-only examples or deterministic filtering, not broad answer contrast.
