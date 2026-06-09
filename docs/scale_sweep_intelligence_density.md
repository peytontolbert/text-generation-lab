# Scale Sweep Intelligence Density

This maps the whole model sweep, not just the 100M target.
Each scale band is evidence about a different part of model intelligence density.

## Breakpoints

- `smallest_answer_999`: `knowledge_compression_stage511_21k_d10_compact_false_claim_1500step` at `20946` params (exact `0.9971264367816092`, answer `0.9990421455938697`, bits/param `None`)
- `smallest_exact_999`: `stage505_16k_retrieval32_1500step` at `16536` params (exact `1.0`, answer `0.9961685823754789`, bits/param `1.3864910841115623`)
- `smallest_exact_and_answer_999`: `stage531_23k_d11_compact_false_claim_900step` at `23369` params (exact `1.0`, answer `1.0`, bits/param `None`)
- `raw_density_leader`: `stage525_16k_rule_replay_from_stage502_2400step` at `16280` params (exact `0.9952107279693486`, answer `0.9971264367816092`, bits/param `1.410325570323004`)
- `training_token_efficiency_leader`: `stage466_90k_compact_membership_cards` at `90176` params (exact `1.0`, answer `1.0`, bits/param `0.2543697266774459`)

## Regimes

- `tokenizer_floor_probe`: Below 10k actual params, embeddings/tokenizer dominate. Useful for lower-bound geometry, not reliable intelligence.
- `raw_density_frontier`: 10k-20k contains the highest raw KBPP points. It shows how much knowledge can fit, but misses residual reliability bits.
- `reliability_breakpoint`: 20k-30k is the current first reliable region for this curriculum: enough width to bind composite knowledge jointly.
- `reliable_but_density_declines`: 30k-100k preserves reliability with lower density. Useful for checking target-design breakpoints.
- `overcapacity_for_current_curriculum`: Above 100k the curriculum saturates; bigger models score well but teach less about density unless tasks get broader/harder.

## Best By Parameter Point

| params | regime | best answer | best bits/param | best exact |
|---:|---|---|---|---|
| 7604 | `tokenizer_floor_probe` | `0.167192429022082` stage471_7k_compact_reverse_comp_key | `1.1370171358904246` stage471_7k_compact_reverse_comp_key | `0.167192429022082` stage471_7k_compact_reverse_comp_key |
| 12974 | `raw_density_frontier` | `None`  | `0.14463755198024733` 1k-400 | `0.2672998643147897` 1k-400 |
| 13598 | `raw_density_frontier` | `None`  | `0.1246905945005826` 1k-100 | `0.24151967435549526` knowledge_compression_ladder_stage429_budget_100_vs_400 |
| 16280 | `raw_density_frontier` | `0.9976053639846744` knowledge_compression_stage539_16k_noaux_polish_after_answer_contrast_3000step | `1.410325570323004` stage525_16k_rule_replay_from_stage502_2400step | `0.9980842911877394` stage539_16k_noaux_polish_after_answer_contrast_3000step |
| 16536 | `raw_density_frontier` | `0.9966475095785441` stage506_16k_retrieval32_2100step | `1.3864910841115623` stage505_16k_retrieval32_1500step | `1.0` stage505_16k_retrieval32_1500step |
| 20946 | `reliability_breakpoint` | `1.0` knowledge_compression_stage522_21k_operation_gated_eval | `1.0987892588007901` stage512_21k_d10_compact_false_claim_2100step | `0.9985632183908046` knowledge_compression_stage522_21k_operation_gated_eval |
| 23369 | `reliability_breakpoint` | `1.0` knowledge_compression_stage533_23k_d11_operation_gated_eval | `None`  | `1.0` stage531_23k_d11_compact_false_claim_900step |
| 25852 | `reliability_breakpoint` | `1.0` stage508_26k_intermediate_d12_900step | `0.8906957961023488` stage557_stage548_verified_density_reference | `1.0` stage508_26k_intermediate_d12_900step |
| 26189 | `reliability_breakpoint` | `0.9995210727969349` stage551_26k_retrieval_controller_2340step | `None`  | `0.9980842911877394` stage551_26k_retrieval_controller_2340step |
| 26866 | `reliability_breakpoint` | `None`  | `0.19252429834506898` 10k-400 | `0.7367706919945726` 10k-400 |
| 28066 | `reliability_breakpoint` | `None`  | `0.11200106417021924` 10k-100 | `0.44776119402985076` 10k-100 |
| 34046 | `reliable_but_density_declines` | `0.9995210727969349` stage571_keyhash_sidecar_low_lr_negative_result | `None`  | `0.9980842911877394` stage554_key_hash_sidechannel |
| 36384 | `reliable_but_density_declines` | `1.0` stage498_36k_compact_false_claim_900step | `0.6325648585873282` stage498_36k_compact_false_claim_900step | `1.0` stage494_36k_direct_fact_key_1200step |
| 60328 | `reliable_but_density_declines` | `1.0` stage480_60k_polish_1200step_compact_reverse_comp_key | `0.3815017871443003` stage491_60k_direct_fact_key_600step | `1.0` stage480_60k_polish_1200step_compact_reverse_comp_key |
| 76224 | `reliable_but_density_declines` | `None`  | `0.08372820820337029` moe_residual_replay_100k | `0.9090909090909091` moe_residual_replay_100k |
| 77664 | `reliable_but_density_declines` | `None`  | `0.07412394969965999` knowledge_compression_stage432_set_reverse_dense_vs_moe_100k | `0.9701726844583988` knowledge_compression_stage432_set_reverse_dense_vs_moe_100k |
| 80000 | `reliable_but_density_declines` | `None`  | `0.07335680280276836` moe-residual-100k-stage432-replay | `0.989010989010989` moe-residual-100k-stage432-replay |
| 81984 | `reliable_but_density_declines` | `None`  | `0.07146795807302904` moe-residual-100k-stage433-op-tokens-replay | `0.9874411302982732` moe-residual-100k-stage433-op-tokens-replay |
| 82432 | `reliable_but_density_declines` | `None`  | `0.07164456548998561` stage439-second-residual-replay | `0.9952904238618524` stage439-second-residual-replay |
| 82560 | `reliable_but_density_declines` | `None`  | `0.07164631749070677` stage442-reverse-lookup-keys-replay | `0.9968602825745683` stage442-reverse-lookup-keys-replay |
| 84992 | `reliable_but_density_declines` | `None`  | `0.13934920873321432` knowledge_compression_stage447_compact_set_ops | `1.0` knowledge_compression_stage447_compact_set_ops |
| 87488 | `reliable_but_density_declines` | `None`  | `None`  | `0.9986431478968792` knowledge_compression_stage448_450_derived_set_intersections |
| 87872 | `reliable_but_density_declines` | `None`  | `None`  | `1.0` stage453_87k_factorized_direct |
| 88896 | `reliable_but_density_declines` | `1.0` stage460_87k_rule_case_sets | `0.18600820876750188` stage460_87k_rule_case_sets | `1.0` stage460_87k_rule_case_sets |
| 90176 | `reliable_but_density_declines` | `1.0` stage465_90k_membership_answer_targets | `0.25498119236657435` stage485_90k_polish_600step_compact_reverse_comp_key | `1.0` stage465_90k_membership_answer_targets |
| 92928 | `reliable_but_density_declines` | `None`  | `0.012300517573728138` moe_top1_100k | `0.1628222523744912` moe_top1_100k |
| 131930 | `overcapacity_for_current_curriculum` | `None`  | `0.05169614871001342` 100k-400 | `0.9715061058344641` 100k-400 |
| 135034 | `overcapacity_for_current_curriculum` | `None`  | `0.052455583690277516` knowledge_compression_stage430_semantic_ops_100k_1m | `0.9674355495251018` 100k-100-residual |
| 515872 | `overcapacity_for_current_curriculum` | `None`  | `None`  | `1.0` stage459_516k_factorized_direct_rule_keys |
| 522784 | `overcapacity_for_current_curriculum` | `1.0` stage462_523k_rule_case_intersections | `0.0440032822520291` stage468_523k_stage464_continued | `1.0` stage462_523k_rule_case_intersections |
| 644922 | `overcapacity_for_current_curriculum` | `None`  | `0.01122096422209891` 1m-stage430 | `0.9830729166666666` 1m-stage430 |
| 13440576 | `large_overcapacity_reference` | `1.0` stage473_13m_compact_reverse_comp_key | `0.0017115495577603801` stage473_13m_compact_reverse_comp_key | `1.0` stage473_13m_compact_reverse_comp_key |
| 13657946 | `large_overcapacity_reference` | `None`  | `0.0005035476069510481` 10m-400 | `0.9796472184531886` 10m-400 |
| 102654362 | `large_overcapacity_reference` | `None`  | `1.3918825206514464e-05` 100m-v429 | `0.20352781546811397` 100m-v429 |

## Main Findings

- The sweep matters because each scale reveals a different failure mode: tokenizer floor, raw density, reliability breakpoint, and overcapacity.
- The current reliable breakpoint is not at 100M; it is already around 23k-26k for the controlled curriculum depending on evaluator strictness, which means the curriculum is too narrow to explain 100M general intelligence by itself.
- For general intelligence, the sweep must be repeated on broader knowledge-unit benchmarks so the 100M rung is not overcapacity.
- The 1k-to-100M program should be treated as a microscope: tiny rungs reveal target entropy and representation failures before expensive larger runs.

## Source

- JSON: `runs/local/artifacts/scale_sweep_intelligence_density.json`
- Tiny map: `runs/local/artifacts/tiny_intelligence_mapping.json`
