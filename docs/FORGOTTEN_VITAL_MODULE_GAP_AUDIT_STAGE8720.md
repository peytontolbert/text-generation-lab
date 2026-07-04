# Stage8720 Forgotten Vital Module Gap Audit

This audit separates modules already recovered from high-value modules still only conceptually indexed.

## Already Covered

- `alignment_dropout_audit`: `ready_partial`
- `cluster_slice_near_duplicate_detector`: `ready_partial`
- `context_packer_lost_in_middle_memory`: `ready_partial`
- `dataset_junk_ood_ranker_v1`: `ready_partial`
- `gradient_activation_interpretability`: `ready_partial`
- `mixed_precision_runtime_contract`: `ready_partial`
- `operator_codelength_interface`: `ready_partial`
- `program_state_extractors`: `ready_partial`
- `repo_graph_encoder`: `ready_partial`
- `rubric_judge_calibrator`: `ready_partial`
- `semantic_flow_extractors`: `ready_partial`
- `state_space_repo_state_compressor`: `ready_partial`
- `training_telemetry_metrics`: `ready_partial`

## Forgotten / Not Yet Recovered

1. `cross_encoder_reranker_calibration` - BM25/dense/hybrid retrieval exists, but evidence ordering still lacks calibrated task-evidence pair scoring.
   - needed: deterministic reranker calibration card over task/evidence pairs with leakage and locked-eval gates
2. `dataset_cartography_active_learning` - Scaling to 1M+ rows needs learnability signals: confidence, variability, forgetting, hard/easy/redundant rows.
   - needed: cartography card and sampler contract; no training authority
3. `training_data_attribution_influence` - Failure-to-data repair loop needs nearest/helpful/harmful example accounting rather than aggregate slice counts only.
   - needed: deterministic attribution placeholder interface using row embeddings/loss metadata before heavy TRAK-style work
4. `fusion_logits_forward_pass_contract` - Model-stack spine mentions fusion, but no local contract defines how structured heads, retrieval confidence, verifier signals, and decoder logits combine.
   - needed: no-execution fusion policy contract with calibrated input requirements and authority gates
5. `moe_lora_adapter_router_contract` - Specialist models/adapters are indexed, but no router contract prevents premature adapter routing before slice gates are reliable.
   - needed: deterministic adapter routing card by language/task/repo slice with abstain fallback
6. `denoise_diffusion_repair_contract` - Denoise rows exist, but no module defines masked-span repair loop, verifier-guided remasking, or when denoise CE can safely reopen.
   - needed: masked repair contract for bad_output -> repaired_output trajectories; training closed
7. `adversarial_hard_negative_generator` - Shortcut/leakage audits catch current leaks, but scaling needs adversarial counterexample generation for proxy features.
   - needed: no-authority hard-negative row generator for shortcut baselines and leakage probes
8. `confidence_ood_head_contract` - Telemetry has entropy/confidence metrics and ranker has OOD score, but no head-level calibration contract exists.
   - needed: confidence/OOD head schema, thresholds, Brier/ECE card, high-confidence-wrong gate
9. `structured_data_operation_curriculum` - Software maintenance spans JSON, tables, graphs, AST, logs, workflows, and memory, but there is no unified operation curriculum contract.
   - needed: state + schema + addressing + operator + validator curriculum rows for non-code structures
10. `semantic_equivalence_metamorphic_verifier` - Runtime verifier loop exists, but semantic equivalence/property/metamorphic checks are only operator names, not concrete verifier contracts.
   - needed: deterministic verifier contract for equivalence, property tests, metamorphic tests, and API compatibility

## Boundary

This is a recovery audit only. It does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, or promotion.
