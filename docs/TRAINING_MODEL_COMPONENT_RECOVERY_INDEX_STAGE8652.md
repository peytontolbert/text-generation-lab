# Stage8652 Model Component Recovery Coverage Audit

This supersedes the colliding Stage8651 component audit and binds the model/training recovery index to a unique stage number. It opens no execution or training authority.

## Result

- Components tracked: `14`
- Implemented or partial: `3`
- Schema/reference only: `5`
- Training/model/decode/runtime authority: closed

## Component Status
- `activation_logit_interpretability`: telemetry_contracts_exist_no_activation_patch_module
  Next: Add token-loss, module-delta, gradient norm, logit margin, entropy, and activation-cache hooks to next tiny probe only; no broad SAE work yet.
- `decoder_only_causal`: bounded_candidate_role_only_training_closed
  Next: Reopen only as tiny bounded probe after budget-clean and contentful-output gates.
- `denoise_diffusion`: objective_restored_but_denoise_ce_closed
  Next: Use as repair-route curriculum first. Only later train masked denoise on bad_output -> repaired_output pairs.
- `encoder_decoder_seq2seq`: current_student_family_recovered
  Next: Use for structured transition heads and bounded arguments only until graph/symbol/data-ranker gates pass.
- `encoder_only_retriever_reranker`: reference_recovered_source_grounding_not_wired_to_all_objectives
  Next: Attach retrieval evidence packets and evidence-removed controls to every scaled row.
- `fusion_logits_forward_pass`: schema_only_no_local_module
  Next: Define a no-execution fusion contract: structured logits + deterministic gates + evidence confidence + verifier result. Implement only after each component is calibrated.
- `gan_adversarial_hard_negative`: schema_only_use_for_dataset_not_generation
  Next: Use to generate adversarial shortcut rows after junk/ranker exists; not part of production decode.
- `gnn_repo_graph`: graph_seed_exists_but_encoder_not_implemented
  Next: Repair repo_state_graph_v1 enrichment with opaque IDs, source-backed nodes/edges, and degree/query-node shortcut audits.
- `heads_blocks_layers_mlp`: target_config_recovered_but_no_fresh_param_probe_after_8650
  Next: Add non-instantiating parameter/head/layer audit into the aggregate gate before training.
- `linear_tree_mlp_classifiers`: concept_and_refs_recovered_not_unified_as_junk_ranker
  Next: Build explicit junk/risk/OOD classifier cards over source-backed rows before scaling.
- `moe_lora_adapters`: schema_only_refs_recovered
  Next: Only add adapters after task/language slice gates are reliable.
- `ngram_markov`: reference_recovered_not_integrated
  Next: Implement as dataset/ranker feature: local syntax prior, repetition risk, style anomaly. Do not make it an authority signal.
- `state_space_mamba`: reference_recovered_no_local_compressor
  Next: Define repo_stream -> compressed_repo_state packet first; no Mamba training until graph/retrieval packets are stable.
- `transition_functions`: partially_implemented_structured_heads
  Next: Keep as finite structured heads until source-backed graph/symbol-binding are repaired.

## Immediate Order

1. Repair `symbol_binding` and `repo_state_graph_v1_enrichment` using recovered `/arxiv/TOLBERT_BRAIN` graph sources.
2. Build junk/risk/OOD ranker cards using linear/tree/MLP classifier references.
3. Add n-gram/repetition/style-prior features as non-authority ranker inputs.
4. Add a no-execution fusion contract over calibrated logits and deterministic gates.
5. Only after these pass, consider SSM/Mamba compression, GNN encoder training, denoise CE, or bounded decoder CE probes.
