# General KBPP Benchmark Spec

Measure broad recoverable, composable, generalizable knowledge bits per parameter for general models.

## Non-Goals

- Do not measure agent/tool use.
- Do not reward verbose explanation unless it recovers additional verified knowledge bits.
- Do not count benchmark leakage or exact memorization as generalization.

## Knowledge Unit Types

- `atomic_fact`: Single recoverable proposition, e.g. entity-property-value.
- `relation`: Typed relation between two or more entities.
- `schema`: Reusable field/type/default structure.
- `exception`: Override to a schema/default rule.
- `procedure`: Ordered transformation or algorithmic step sequence.
- `causal_rule`: If/then or intervention-style relation with directionality.
- `math_identity`: Symbolic or numerical identity with variable substitution.
- `code_api_semantics`: Function/class/API behavior and constraints.
- `composition`: Multi-unit query requiring joins, chains, intersections, or rule application.
- `counterfactual_false_claim`: Incorrect claim with recoverable correction.

## Benchmark Families

### atomic_recovery
- Unit types: `atomic_fact, relation, schema, exception`
- Measures: `recoverable_knowledge_bits_per_param, binding_reliability`
- Split controls: `held_out_entities, held_out_domains, paraphrased_queries`

### composition_recovery
- Unit types: `composition, relation, schema, exception`
- Measures: `composition_depth_per_param, binding_reliability`
- Split controls: `held_out_composition_graphs, depth, branching_factor, distractors`

### procedural_knowledge
- Unit types: `procedure, code_api_semantics, math_identity`
- Measures: `generalization_bits_per_param, compute_efficiency`
- Split controls: `held_out_parameters, held_out_surface_forms, held_out_api_names`

### false_claim_correction
- Unit types: `counterfactual_false_claim, exception, causal_rule`
- Measures: `negative_knowledge_bits_per_param, binding_reliability`
- Split controls: `near_miss_claims, field_swaps, entity_swaps`

### abstraction_reuse
- Unit types: `schema, procedure, causal_rule, math_identity`
- Measures: `reuse_factor, generalization_bits_per_param`
- Split controls: `new_entities_under_seen_schema, new_schema_combinations, new_variable_bindings`

## Bit Accounting

- `verified_bits`: sum(correct_unit_i * log2(candidate_space_i))
- `kbpp`: verified_bits / parameter_count
- `generalization_kbpp`: verified_bits_on_hidden_unit_splits / parameter_count
- `composition_kbpp`: verified_bits_on_multi_unit_queries / parameter_count
- `eid`: sum(verified_bits_i * reliability_i * generalization_i * composition_depth_weight_i) / (parameters * inference_compute_i)
- `reliability_gate`: Report raw density separately from thresholds; promotion requires exact/answer reliability across all required families.

## 100M vs 7B Go/No-Go

- `primary`: 100M generalization KBPP and EID exceed measured 7B baseline by margin on hidden units.
- `minimum_margin`: >=1.25x on EID and >=1.10x on generalization KBPP before claiming route is engineering-ready.
- `failure_condition`: If 100M only wins memorized KBPP but loses generalization or composition, route is not sufficient.

## Dataset Construction Rules

- Every unit must have a finite or calibrated candidate space.
- Every answer must be verifier-checkable.
- Natural-language paraphrases must map back to the same canonical unit.
- Composition examples must reference source unit ids and graph depth.
- Training-visible and hidden units must be explicitly marked.
- Generated synthetic units and natural mined units must be tracked separately.
- Candidate distractors must include near misses, field swaps, relation swaps, and entity swaps.

## Next Build Steps

- Create a JSONL knowledge-unit dataset with this schema.
- Build a verifier that scores exact, answer-equivalent, and compositional answers.
- Measure a 7B baseline useful-KBPP on the same hidden-unit splits.
- Train 10M/30M/100M ladder models with factorized knowledge supervision.
- Fit KBPP/EID scaling curves and only then decide whether the 100M route is non-experimental.

## Source

- Spec JSON: `runs/local/artifacts/general_kbpp_benchmark_spec.json`
- Unit schema JSON: `runs/local/artifacts/knowledge_unit_schema.json`
