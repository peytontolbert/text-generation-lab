# Tiny Intelligence Mapping

Generated: 2026-05-28T16:28:19Z

This map treats intelligence narrowly: verified semantic access under fixed
parameter, token, and runtime contracts. It is not yet a general intelligence
benchmark, but it is a usable parameter-space map for compressed knowledge
retrieval, binding, rule use, set operations, and verifier-assisted access.

## Global Frontier

- best_exact_top1: `knowledge_compression_stage447_compact_set_ops`
  - params: `84992`
  - steps: `300`
  - exact_top1: `1.0`
  - verified_bits_per_million_params: `139349.20873321433`
  - verified_bits_per_training_token: `0.0063088531494871975`
- best_answer_top1: `knowledge_compression_stage533_23k_d11_operation_gated_eval`
  - params: `23369`
  - steps: `1800`
  - exact_top1: `0.9985632183908046`
  - answer_top1: `1.0`
- best_verified_bits_per_million_params: `stage525_16k_rule_replay_from_stage502_2400step`
  - params: `16280`
  - steps: `2400`
  - exact_top1: `0.9952107279693486`
  - answer_top1: `0.9971264367816092`
  - verified_bits_per_million_params: `1410325.570323004`
- best_verified_bits_per_training_token: `stage466_90k_compact_membership_cards`
  - params: `90176`
  - steps: `300`
  - exact_top1: `1.0`
  - answer_top1: `1.0`
  - verified_bits_per_million_params: `254369.72667744587`
  - verified_bits_per_training_token: `0.08558238092976941`

## Best By Parameter Band

Rows can come from different curriculum scopes, so a frontier value is a
measurement waypoint rather than a universal winner. Use the JSON records
when comparing only runs from the same curriculum family.

| band | best exact | best answer | best bits/Mparam | best bits/token |
|---|---|---|---|---|
| 100k-1m | `1.0`<br>stage459_516k_factorized_direct_rule_keys | `1.0`<br>stage462_523k_rule_case_intersections | `52455.58369027752`<br>knowledge_compression_stage430_semantic_ops_100k_1m | `0.0729265582132149`<br>stage470_523k_compact_reverse_comp_key |
| 10k-20k | `1.0`<br>stage505_16k_retrieval32_1500step | `0.9976053639846744`<br>knowledge_compression_stage539_16k_noaux_polish_after_answer_contrast_3000step | `1410325.570323004`<br>stage525_16k_rule_replay_from_stage502_2400step | `0.06918404419459909`<br>stage503_16k_retrieval32_300step |
| 10m+ | `1.0`<br>stage473_13m_compact_reverse_comp_key | `1.0`<br>stage473_13m_compact_reverse_comp_key | `1711.5495577603801`<br>stage473_13m_compact_reverse_comp_key | `0.07296153497974403`<br>stage473_13m_compact_reverse_comp_key |
| 20k-30k | `1.0`<br>stage508_26k_intermediate_d12_900step | `1.0`<br>knowledge_compression_stage533_23k_d11_operation_gated_eval | `1098789.2588007902`<br>stage512_21k_d10_compact_false_claim_2100step | `0.0727516743805693`<br>stage507_26k_intermediate_d12_300step |
| 30k-50k | `1.0`<br>stage494_36k_direct_fact_key_1200step | `1.0`<br>stage498_36k_compact_false_claim_900step | `632564.8585873282`<br>stage498_36k_compact_false_claim_900step | `0.07285660468015666`<br>stage497_36k_compact_false_claim_300step |
| 50k-100k | `1.0`<br>knowledge_compression_stage447_compact_set_ops | `1.0`<br>stage460_87k_rule_case_sets | `381501.7871443003`<br>stage491_60k_direct_fact_key_600step | `0.08558238092976941`<br>stage466_90k_compact_membership_cards |
| <10k | `0.167192429022082`<br>stage471_7k_compact_reverse_comp_key | `0.167192429022082`<br>stage471_7k_compact_reverse_comp_key | `1137017.1358904247`<br>stage471_7k_compact_reverse_comp_key | `0.027421784958829968`<br>stage471_7k_compact_reverse_comp_key |

## Compute Proxies

The JSON map includes compute proxies for records with enough data:

- `training_param_steps_proxy = params * steps`
- `training_param_token_proxy = params * estimated_training_retrieval_tokens`
- `verified_bits_per_param = verified_bits_per_million_params / 1_000_000`

These are not hardware FLOPs. They are stable local proxies for comparing
runs that share this training stack and curriculum family.

## Pareto Frontiers

Smallest parameter counts that improve answer top1:

- `7604` params: answer `0.167192429022082` - stage471_7k_compact_reverse_comp_key
- `16280` params: answer `0.9976053639846744` - knowledge_compression_stage539_16k_noaux_polish_after_answer_contrast_3000step
- `20946` params: answer `1.0` - knowledge_compression_stage522_21k_operation_gated_eval

Smallest parameter counts that improve exact top1:

- `7604` params: exact `0.167192429022082` - stage471_7k_compact_reverse_comp_key
- `12974` params: exact `0.2672998643147897` - 1k
- `16280` params: exact `0.9980842911877394` - stage539_16k_noaux_polish_after_answer_contrast_3000step
- `16536` params: exact `1.0` - stage505_16k_retrieval32_1500step

## Current Read

- The current best pure-neural strict checkpoint remains Stage548.
- Deterministic structured-key hard filtering is the best verified runtime contract.
- Learned key-hash side channels are negative so far, including when active during the full Stage548-style continuation.
- The map is strongest for semantic access and weakest for free-form decoding, planning, and broad transfer.
- Runtime-only verifier rows without parameter counts are kept in the JSON records but omitted from the band table.

## Source

- JSON map: `runs/local/artifacts/tiny_intelligence_mapping.json`
- Ledger: `runs/ledgers/pocketpal_seq2seq_runs.jsonl`
