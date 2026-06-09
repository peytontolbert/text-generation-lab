# Knowledge Bits Per Parameter

Generated: 2026-05-28T16:36:03Z

This report ranks runs by verified semantic bits per raw parameter.
Higher is better only within comparable curriculum families; reliability
threshold sections separate dense-but-imperfect runs from high-confidence
frontier candidates.

## Main Findings

- The highest raw bits/param point is in the 16k band, but it is not answer-perfect.
- The best exact+answer-perfect high-reliability point is currently the 26k Stage508 run.
- Compact false-claim/card designs and direct keying move the reliability frontier downward.
- Learned key hashes and auxiliary anchors are negative for Stage548 because they collapse membership proof geometry.

## Overall Leaders

- `1.41033` bits/param, `16280` params: stage525_16k_rule_replay_from_stage502_2400step
- `1.40626` bits/param, `16280` params: stage502_16k_compact_false_claim_2100step
- `1.40558` bits/param, `16280` params: stage501_16k_compact_false_claim_1500step
- `1.39813` bits/param, `16280` params: stage500_16k_compact_false_claim_900step
- `1.38865` bits/param, `16280` params: stage475_16k_continued_1200step_compact_reverse_comp_key
- `1.38649` bits/param, `16536` params: stage505_16k_retrieval32_1500step
- `1.38582` bits/param, `16536` params: stage506_16k_retrieval32_2100step
- `1.38316` bits/param, `16536` params: stage504_16k_retrieval32_900step
- `1.37104` bits/param, `16280` params: stage474_16k_continued_compact_reverse_comp_key
- `1.32023` bits/param, `16280` params: stage499_16k_compact_false_claim_300step

## High-Reliability Leaders

### answer>=0.999
- `1.09879` bits/param, exact `0.9980842911877394`, answer `0.9995210727969349`, `20946` params: stage512_21k_d10_compact_false_claim_2100step
- `1.09879` bits/param, exact `0.9976053639846744`, answer `0.9995210727969349`, `20946` params: stage513_21k_d10_compact_false_claim_2700step
- `1.09879` bits/param, exact `0.9980842911877394`, answer `0.9995210727969349`, `20946` params: stage522_21k_rule_replay_from_stage512_2400step
- `1.09879` bits/param, exact `0.9980842911877394`, answer `0.9995210727969349`, `20946` params: stage527_21k_same_op_hardneg_from_stage512_2400step
- `1.09879` bits/param, exact `0.9976053639846744`, answer `0.9995210727969349`, `20946` params: stage529_21k_rule_field_hardneg_from_stage512_2400step
- `1.09826` bits/param, exact `0.9971264367816092`, answer `0.9990421455938697`, `20946` params: stage511_21k_d10_compact_false_claim_1500step
- `1.09826` bits/param, exact `0.9980842911877394`, answer `0.9990421455938697`, `20946` params: stage524_21k_rule_reverse_replay_from_stage522_2700step
- `0.890269` bits/param, exact `0.9976053639846744`, answer `0.9995210727969349`, `25852` params: stage565_eval_residual_replay_pipeline_and_negative_training_result

### exact>=0.999
- `1.38649` bits/param, exact `1.0`, answer `0.9961685823754789`, `16536` params: stage505_16k_retrieval32_1500step
- `0.889843` bits/param, exact `1.0`, answer `1.0`, `25852` params: stage508_26k_intermediate_d12_900step
- `0.632565` bits/param, exact `1.0`, answer `1.0`, `36384` params: stage498_36k_compact_false_claim_900step
- `0.631959` bits/param, exact `1.0`, answer `0.9995210727969349`, `36384` params: stage494_36k_direct_fact_key_1200step
- `0.631959` bits/param, exact `1.0`, answer `0.9995210727969349`, `36384` params: stage496_36k_false_key_full_card_900step
- `0.631352` bits/param, exact `1.0`, answer `0.9985632183908046`, `36384` params: stage497_36k_compact_false_claim_300step
- `0.381502` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage491_60k_direct_fact_key_600step
- `0.381136` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage480_60k_polish_1200step_compact_reverse_comp_key

### exact>=0.999_and_answer>=0.999
- `0.889843` bits/param, exact `1.0`, answer `1.0`, `25852` params: stage508_26k_intermediate_d12_900step
- `0.632565` bits/param, exact `1.0`, answer `1.0`, `36384` params: stage498_36k_compact_false_claim_900step
- `0.631959` bits/param, exact `1.0`, answer `0.9995210727969349`, `36384` params: stage494_36k_direct_fact_key_1200step
- `0.631959` bits/param, exact `1.0`, answer `0.9995210727969349`, `36384` params: stage496_36k_false_key_full_card_900step
- `0.381502` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage491_60k_direct_fact_key_600step
- `0.381136` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage480_60k_polish_1200step_compact_reverse_comp_key
- `0.381136` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage482_60k_count2_replay_1350step_compact_reverse_comp_key
- `0.380588` bits/param, exact `1.0`, answer `1.0`, `60328` params: stage490_60k_direct_fact_key_300step

## Best By Band

| band | median bits/param | best bits/param | best run |
|---|---:|---:|---|
| 100k-1m | 0.0451746 | 0.0524556 | knowledge_compression_stage430_semantic_ops_100k_1m |
| 10k-20k | 1.3771 | 1.41033 | stage525_16k_rule_replay_from_stage502_2400step |
| 10m+ | 0.000497968 | 0.00171155 | stage473_13m_compact_reverse_comp_key |
| 20k-30k | 1.05193 | 1.09879 | stage512_21k_d10_compact_false_claim_2100step |
| 30k-50k | 0.631352 | 0.632565 | stage498_36k_compact_false_claim_900step |
| 50k-100k | 0.0744272 | 0.381502 | stage491_60k_direct_fact_key_600step |
| <10k | 1.13702 | 1.13702 | stage471_7k_compact_reverse_comp_key |

## Target Design Buckets

- compact_false_claim: best `1.40626` bits/param from `stage502_16k_compact_false_claim_2100step`
- compact_reverse_or_reverse_replay: best `1.38865` bits/param from `stage475_16k_continued_1200step_compact_reverse_comp_key`
- direct_fact_keying: best `0.631959` bits/param from `stage494_36k_direct_fact_key_1200step`
- other: best `1.09879` bits/param from `stage527_21k_same_op_hardneg_from_stage512_2400step`
- retrieval_head_dim_32: best `1.38649` bits/param from `stage505_16k_retrieval32_1500step`
- rule_replay_or_rule_keying: best `1.41033` bits/param from `stage525_16k_rule_replay_from_stage502_2400step`

## 16k Density Frontier Diagnosis

Stage525 remains the raw density leader at `1.41033` verified bits/param, but the new residual analysis shows this is a dense-but-imperfect point, not a reliable model. Its batch-local score is exact `0.9952107279693486` / answer `0.9971264367816092`, and operation-gated evaluation still leaves `7` strict top-1 misses and `4` answer misses.

The residual is mostly composite proof geometry: `set_intersection_member`, `set_intersection_count`, `rule_case_intersection_count`, `rule_case_intersection_member`, and `two_hop_owner_region`. Stage537 broad composite replay keeps `7/8` operation-gated misses shared with Stage525 and does not improve answer reliability. Stage538 answer contrast cuts operation-gated answer misses to `2`, but regresses ungated behavior to `10` answer misses. Stage539 no-aux polish restores batch-local answer to `0.9976053639846744`, but strict full-corpus operation-gated ranking exposes `53` same-operation top-1 confusions.

Current decision: do not spend the next run on another broad 16k replay. The 16k band is the raw bits/parameter frontier; the 26k Stage508/Stage548 family is the reliable tiny-intelligence frontier. The next 16k work should redesign composite proof-card targets or keep deterministic operation/key filtering outside the tiny neural embedding path.

Analysis artifact: `runs/local/artifacts/knowledge_compression_16k_density_frontier_failure_analysis.json`

Stage579 tested the obvious compact-membership target variant and rejected it. Starting from Stage525, `compact_membership_cards=1` reduced repeated fields in membership targets, but over-compressed the proof cards: batch-local exact/answer fell to `0.9540229885057471` / `0.9703065134099617`, and strict full-corpus operation-gated exact/answer fell to `0.8563218390804598` / `0.9305555555555556`. The target lesson is sharper now: the next 16k design must reduce irrelevant text while preserving explicit entity and constraint anchors; minimal key/member/count cards are too aliasable.

Stage579 summary: `runs/local/artifacts/knowledge_compression_stage579_compact_membership_negative_summary.json`

## Operation-Level Bits/Param

Added an operation-level decomposition across `1,395` operation/run rows. This separates two questions that were previously blended:

- How many answer-equivalent bits/param can a tiny model retain for each semantic operation?
- Which missing operation bits prevent a single checkpoint from being reliable?

The highest individual operation density is `rule_case_intersection_member` in a 16k run: Stage539 reaches `0.244538` answer bits/param for that operation. But operation-level frontiers are not composable by themselves; different 16k checkpoints solve different operations. Stage525's missing answer bits are individually tiny, about `0.000677` bits/param per missed eval row, but they are distributed across `rule_case_intersection_member`, `set_member`, `two_hop_owner_region`, `rule_case_intersection_count`, `set_intersection_count`, and `direct_fact`. Stage508 has zero missing answer bits across the focus operations, which is why it remains the reliable 26k frontier despite lower raw density.

The composability gap is now quantified. In the `10k-20k` band, the operation oracle reaches `1.413712519339149` answer bits/param, while the best single run reaches `1.4110029601262326`; the gap is only `0.0019166267369430205` of the oracle. So the 16k problem is not mainly that different checkpoints solve different operations. The best 16k checkpoint is already close to the band oracle, but it is still a few residual answer bits short of reliability. In the `20k-30k` band, the raw-density leader is Stage512, while Stage508 is the reliable checkpoint; this cleanly separates raw compression from trustworthy intelligence.

Operation report: `runs/local/artifacts/operation_bits_per_param_report.json`
