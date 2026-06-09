# Operation Bits Per Parameter

This decomposes verified semantic bits/parameter by operation.
It uses each operation's evaluated pair count, exact/answer top1, and the eval-card choice entropy from the run artifact.

## Main Findings

- Run-level bits/param rewards small models with many near-correct operations, so reliability thresholds must be tracked separately.
- Operation-level frontiers show what each tiny run can solve, but the best operations are not necessarily solved simultaneously in one checkpoint.
- This report uses batch-local retrieval evals where available; strict full-corpus operation-gated eval remains the promotion-grade reliability check.
- The 16k frontier keeps high raw operation bits/param on most operations but loses its missing bits in composite membership/count operations.
- The 26k frontier gives up raw density but clears the reliability threshold across the full operation mix.
- Stage579 confirms that lowering target text entropy without preserving discriminative anchors destroys operation-level bits/param.
- The 16k operation-oracle gap is tiny (0.192%), so the remaining issue is not mainly that different checkpoints solve different operations; the best 16k checkpoint is a few residual bits short of joint reliability.
- In the 20k-30k band, the raw-density leader is not the reliability leader: stage512_21k_d10_compact_false_claim_2100step has higher summed operation bits/param, while stage508_26k_intermediate_d12_900step is the reliable checkpoint.

## Highest Operation-Level Answer Bits/Param

- `0.244538` bits/param, answer `1.0`, `rule_case_intersection_member`: stage539_16k_noaux_polish_after_answer_contrast_3000step
- `0.24386` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage525_16k_rule_replay_from_stage502_2400step
- `0.24386` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage537_16k_composite_replay_2700step
- `0.24386` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage538_16k_composite_answer_contrast_2700step
- `0.242506` bits/param, answer `0.9916897506925207`, `rule_case_intersection_member`: stage475_16k_continued_1200step_compact_reverse_comp_key
- `0.242506` bits/param, answer `0.9916897506925207`, `rule_case_intersection_member`: stage500_16k_compact_false_claim_900step
- `0.242506` bits/param, answer `0.9916897506925207`, `rule_case_intersection_member`: stage501_16k_compact_false_claim_1500step
- `0.242506` bits/param, answer `0.9916897506925207`, `rule_case_intersection_member`: stage502_16k_compact_false_claim_2100step
- `0.241828` bits/param, answer `0.9889196675900277`, `rule_case_intersection_member`: stage474_16k_continued_compact_reverse_comp_key
- `0.240085` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage504_16k_retrieval32_900step
- `0.240085` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage505_16k_retrieval32_1500step
- `0.240085` bits/param, answer `0.997229916897507`, `rule_case_intersection_member`: stage506_16k_retrieval32_2100step

## Composability Gap

The operation oracle picks the best checkpoint separately for each operation inside a scale band.
The single-run score is what one checkpoint actually contains.

| band | operation oracle answer bits/param | best single run | gap | gap fraction | best reliable run |
|---|---:|---:|---:|---:|---|
| 100k-1m | 0.0451923 | 0.0440033 | 0.00118898 | 0.026 | `stage459_516k_factorized_direct_rule_keys` |
| 10k-20k | 1.41371 | 1.411 | 0.00270956 | 0.002 | `` |
| 10m+ | 0.00171319 | 0.00171319 | 0 | 0.000 | `stage473_13m_compact_reverse_comp_key` |
| 20k-30k | 1.09932 | 1.09879 | 0.000526492 | 0.000 | `stage508_26k_intermediate_d12_900step` |
| 30k-50k | 0.632868 | 0.632868 | 0 | 0.000 | `stage498_36k_compact_false_claim_900step` |
| 50k-100k | 0.381685 | 0.381685 | -5.55112e-17 | -0.000 | `stage491_60k_direct_fact_key_600step` |
| <10k | 1.13702 | 1.13702 | 0 | 0.000 | `` |

## Reliable Operation Frontiers

| operation | best reliable answer bits/param | run | params | answer |
|---|---:|---|---:|---:|
| `direct_fact` | 0.211408 | `stage505_16k_retrieval32_1500step` | 16536 | 1.0 |
| `entity_context` | 0.024386 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `exception` | 0.0216765 | `stage501_16k_compact_false_claim_1500step` | 16280 | 1.0 |
| `false_claim` | 0.0203217 | `stage499_16k_compact_false_claim_300step` | 16280 | 1.0 |
| `reverse_lookup_set` | 0.108382 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `rule_case_count` | 0.00812868 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `rule_case_intersection_count` | 0.125317 | `stage538_16k_composite_answer_contrast_2700step` | 16280 | 1.0 |
| `rule_case_intersection_member` | 0.244538 | `stage539_16k_noaux_polish_after_answer_contrast_3000step` | 16280 | 1.0 |
| `rule_case_member` | 0.0182895 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `rule_default` | 0.039966 | `stage501_16k_compact_false_claim_1500step` | 16280 | 1.0 |
| `set_count` | 0.123962 | `stage475_16k_continued_1200step_compact_reverse_comp_key` | 16280 | 1.0 |
| `set_intersection_count` | 0.0731581 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `set_intersection_member` | 0.131414 | `stage474_16k_continued_compact_reverse_comp_key` | 16280 | 1.0 |
| `set_member` | 0.234377 | `stage502_16k_compact_false_claim_2100step` | 16280 | 1.0 |
| `two_hop_owner_region` | 0.0257408 | `stage499_16k_compact_false_claim_300step` | 16280 | 1.0 |

## Missing Bits In Focus Runs

### knowledge_compression_moe_residual_10k_stage579_stage525_compact_membership_cards_lr1e4_steps300
- `0.0189669` missing answer bits/param, answer `0.9224376731301939`: `rule_case_intersection_member`
- `0.0108382` missing answer bits/param, answer `0.953757225433526`: `set_member`
- `0.00474173` missing answer bits/param, answer `0.9639175257731959`: `set_intersection_member`
- `0.00270956` missing answer bits/param, answer `0.8888888888888888`: `entity_context`
- `0.00135478` missing answer bits/param, answer `0.9936908517350158`: `direct_fact`
- `0.00067739` missing answer bits/param, answer `0.9666666666666667`: `false_claim`

### stage508_26k_intermediate_d12_900step
- `0` missing answer bits/param, answer `1.0`: `direct_fact`
- `0` missing answer bits/param, answer `1.0`: `entity_context`
- `0` missing answer bits/param, answer `1.0`: `exception`
- `0` missing answer bits/param, answer `1.0`: `false_claim`
- `0` missing answer bits/param, answer `1.0`: `reverse_lookup_set`
- `0` missing answer bits/param, answer `1.0`: `rule_case_count`

### stage525_16k_rule_replay_from_stage502_2400step
- `0.00067739` missing answer bits/param, answer `0.997229916897507`: `rule_case_intersection_member`
- `0.00067739` missing answer bits/param, answer `0.9971098265895953`: `set_member`
- `0.00067739` missing answer bits/param, answer `0.9736842105263158`: `two_hop_owner_region`
- `0.00067739` missing answer bits/param, answer `0.9945945945945946`: `rule_case_intersection_count`
- `0.00067739` missing answer bits/param, answer `0.9907407407407407`: `set_intersection_count`
- `0.00067739` missing answer bits/param, answer `0.9968454258675079`: `direct_fact`

### stage537_16k_composite_replay_2700step
- `0.00135478` missing answer bits/param, answer `0.9936908517350158`: `direct_fact`
- `0.00067739` missing answer bits/param, answer `0.997229916897507`: `rule_case_intersection_member`
- `0.00067739` missing answer bits/param, answer `0.9736842105263158`: `two_hop_owner_region`
- `0.00067739` missing answer bits/param, answer `0.9945945945945946`: `rule_case_intersection_count`
- `0.00067739` missing answer bits/param, answer `0.9907407407407407`: `set_intersection_count`
- `0` missing answer bits/param, answer `1.0`: `entity_context`

### stage538_16k_composite_answer_contrast_2700step
- `0.00203217` missing answer bits/param, answer `0.9166666666666666`: `entity_context`
- `0.00203217` missing answer bits/param, answer `0.9905362776025236`: `direct_fact`
- `0.00067739` missing answer bits/param, answer `0.997229916897507`: `rule_case_intersection_member`
- `0.00067739` missing answer bits/param, answer `0.9971098265895953`: `set_member`
- `0.00067739` missing answer bits/param, answer `0.9736842105263158`: `two_hop_owner_region`
- `0.00067739` missing answer bits/param, answer `0.9830508474576272`: `rule_default`

## Source

- JSON: `runs/local/artifacts/operation_bits_per_param_report.json`
- Source map: `runs/local/artifacts/tiny_intelligence_mapping.json`
