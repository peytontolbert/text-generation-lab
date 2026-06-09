# Model Intelligence Density Framework

A smaller model can be more intelligent than a larger model only if it has higher effective intelligence density: more recoverable, composable, generalizable knowledge per parameter and per unit inference compute.

## Working Equation

`EID = sum_i(verified_bits_i * reliability_i * generalization_i * composition_depth_weight_i) / (parameters * inference_compute_i)`

- KBPP is the storage term, not the whole intelligence term.
- A model with high KBPP but low binding reliability is dense but not reliably intelligent.
- A model with high memorized KBPP but low generalization has knowledge storage, not broad intelligence.
- A 100M model beats a 7B generally only when its EID advantage exceeds the 70x parameter deficit at comparable task breadth.

## Intelligence Axes

### recoverable_knowledge_bits_per_param
- Question: How many distinct facts, relations, procedures, schemas, and rules can be recovered per parameter?
- Current metric: verified answer bits per parameter
- Current status: implemented for structured semantic curricula
- Next metric: general KBPP over atomic, relational, procedural, and compositional natural knowledge units

### binding_reliability
- Question: Are the right pieces of knowledge retrieved/generated together in one checkpoint, not just somewhere in the run family?
- Current metric: exact/answer top1 plus operation-oracle vs best-single-run composability gap
- Current status: 16k oracle gap is small, but 16k still misses residual answer bits; 26k clears reliability
- Next metric: joint reliability over broad knowledge categories and paraphrase forms

### composition_depth_per_param
- Question: Can stored knowledge be recombined into unseen multi-hop answers?
- Current metric: derived set intersections, rule-case intersections, two-hop owner-region operations
- Current status: measured in controlled curricula; composite membership remains the 16k bottleneck
- Next metric: held-out composition graphs with depth, branching factor, and distractor controls

### generalization_bits_per_param
- Question: How many useful bits transfer to unseen formulations rather than memorized rows?
- Current metric: not fully separated from retrieval-card recovery
- Current status: open gap
- Next metric: train/test split by entity, schema, relation template, paraphrase, and composition graph

### compute_efficiency
- Question: How many verified useful bits are available per inference and training compute unit?
- Current metric: verified bits per training token and params*steps proxies
- Current status: implemented as proxy in tiny_intelligence_mapping
- Next metric: verified bits per measured FLOP and latency at fixed answer quality

### abstraction_reuse
- Question: Does one learned parameter pattern serve many facts/tasks, or only one memorized card?
- Current metric: indirectly visible through density shifts from target factorization
- Current status: target design moved reliable density by about 20x in controlled setting
- Next metric: reuse factor: verified held-out bits gained per explicitly trained bit

## Quantitative Anchors

- `required_100m_vs_7b_kbpp_multiplier_if_7b_fully_utilized`: `70.0`
- `observed_reliable_kbpp_bridge`: `20.231886729514734`
- `observed_raw_kbpp_bridge`: `32.06583493892847`
- `remaining_multiplier_after_reliable_bridge`: `3.459884929954774`
- `remaining_multiplier_after_raw_bridge`: `2.1830088046458074`
- `10k_20k_operation_oracle_gap_fraction`: `0.0019166267369430205`
- `tiny_map_record_count`: `239`

## Research Implications

- The route to powerful smaller models is not only better memorization; it is higher recoverable knowledge density plus reliable binding and reusable abstractions.
- Current evidence says target representation can move density by tens of times, but broad general intelligence needs a general KBPP benchmark and generalization-bit accounting.
- The next decisive map is not another narrow replay run; it is a general knowledge-unit benchmark with scale ladders and 7B useful-KBPP baselines.
- Once the broad ladder predicts a 100M EID advantage over the measured 7B baseline with margin, the route becomes engineering rather than exploration.

## Next Artifacts

- `general_kbpp_benchmark_spec`
- `knowledge_unit_schema`
- `generalization_bits_per_param_ladder`
- `7b_useful_kbpp_baseline`
- `100m_eid_go_no_go_gate`

## Source

- JSON: `runs/local/artifacts/model_intelligence_density_framework.json`
- 100M KBPP route: `runs/local/artifacts/100m_general_kbpp_route_map.json`
- Operation bits report: `runs/local/artifacts/operation_bits_per_param_report.json`
- Tiny intelligence map: `runs/local/artifacts/tiny_intelligence_mapping.json`
