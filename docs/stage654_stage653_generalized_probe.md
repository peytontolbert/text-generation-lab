# Stage654 Stage653 Generalized Probe

Summary: `runs/local/artifacts/stage654_stage653_generalized_probe_summary.json`

Bundle: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage654_stage653_generalized_probe_lr1e6_steps40`

Fast eval: `runs/local/artifacts/stage654_stage653_generalized_probe_fast_eval.json`

## Result

- Surface perfect ceiling: `18.316686398390008` generalized KBPP
- Target: `8.0` no-filter generalized answer KBPP
- No-filter exact/answer KBPP: `0.04628438421402501` / `0.5980970239563056`
- No-filter exact/answer accuracy: `0.002334180248290678` / `0.029394145958563135`
- Answer verified bits: `9737.019550008656` of `298195.65456579486`

## Family Read

| family | exact KBPP bits | answer bits | answer recovery |
|---|---:|---:|---:|
| `abstractions` | 264.0 | 348.0 | 0.050347222222222224 |
| `atomic_facts` | 198.0 | 612.0 | 0.004918981481481482 |
| `counterfactual_and_negative_knowledge` | 6.0 | 438.0 | 0.0079175704989154 |
| `multi_hop_compositions` | 84.0 | 396.0 | 0.006144107242599143 |
| `procedures` | 162.0 | 276.0 | 0.030483764082173626 |
| `relations_and_sets` | 39.50977500432693 | 7667.019550008656 | 0.20154274669499717 |

## Decision

Rejected as a trained 8-KBPP rung. Accepted as a diagnostic.

The surface has enough verified entropy, but direct continuation does not transfer the Stage651 retrieval geometry to the generalized unit mix. The next step is `stage655_generalized_bridge_curriculum`: staged family exposure plus compact selectors for facts, relations, and compositions before another 8-KBPP acceptance run.
