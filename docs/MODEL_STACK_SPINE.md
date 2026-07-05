# v2.7 100M Model-Stack Spine

This document is the canonical model-stack spine for the v2.7 100M software-maintainer project. It complements `docs/recovery_v27_100m/00_central_research_spine.md`.

## Purpose

The research spine tracks the staged objective.

The model-stack spine tracks which model families belong in the full maintainer architecture, what each family is allowed to do, and how signals fuse without turning every component into uncontrolled free-form generation.

## Final System Shape

The target system is not one tiny ChatGPT clone.

It is a multi-model software-maintenance loop:

```text
user intent / repo / logs / tests
-> structured observation
-> evidence retrieval
-> repo graph grounding
-> long-context compression
-> structured transition policy
-> bounded candidate decode
-> verifier / judge / ranker
-> denoising or repair
-> curriculum compiler
-> next dataset version
```

The 100M seq2seq model is the student controller inside this loop. It should learn safe state transitions, bounded arguments, repair transforms, and structured policy labels. It should not be responsible for remembering every repository, authorizing its own body emission, or proving patch correctness without external evidence.

## Research Law

```text
learned logits propose
deterministic gates constrain
symbolic verifiers authorize
dataset judge decides what can enter training
curriculum compiler decides what gap to fill next
```

No learned head alone authorizes source/body emission, runtime execution, Gemma comparison, promotion, or hidden scoring.

## Loop Phases

The model stack is organized around the actual maintainer loop:

```text
observe -> orient -> plan -> act -> verify -> repair -> learn
```

Each model family must have a concrete input, output, validator, and authority boundary.


## Low-Level Training Mechanics Layer

Stage8698 re-grepped Codex sessions for foundational AI/training mechanics so these concepts do not get lost behind high-level module names. These are not optional theory notes; they are the substrate that determines whether the recovered 100M maintainer can be trained, audited, and debugged correctly.

| Mechanic | Role in the 100M maintainer | Current recovery status |
| --- | --- | --- |
| Tensor shape / dtype / device | Prevent invalid batches, broken masks, bad head dimensions, CPU/GPU mismatches | indexed / partially executable |
| MatMul / dot product / linear projection | Core of embeddings, attention projections, MLPs, classifiers, retrieval heads | indexed / partially executable |
| Embeddings / tokenizer / vocab | Converts structured text/code/control tokens into trainable vectors; guards vocab compatibility | indexed / partially executable |
| Attention / QKV / masks | Routes evidence across tokens; controls causal vs encoder-decoder visibility | indexed / partially executable |
| Positional encoding / RoPE | Preserves token/order/location information for code, traces, and graph packets | indexed / partially executable |
| MLP / activation / normalization | Per-token feature transformation; stability through GELU/SiLU and LayerNorm/RMSNorm | indexed / partially executable |
| Logits / CE / loss masks | Converts predictions into supervised gradients while keeping decoder/denoise/runtime losses closed unless authorized | indexed / partially executable |
| Autograd / backward / gradients | Explains how failures change parameters; required for gradient norm and attribution telemetry | indexed / partially executable |
| Optimizer / scheduler | Controls parameter updates; AdamW, warmup, cosine, weight decay must be logged in training cards | indexed / partially executable |
| Dataset / dataloader / batching | Preserves split boundaries, row ordering controls, collate rules, loss masks, and caps | indexed / partially executable |
| Checkpoint / seed / reproducibility | Required for repeatable probes and rollback; no final checkpoint export unless explicitly authorized | indexed / partially executable |
| Mixed precision / memory | Precision and memory policy contract; execution/training still closed unless separately authorized | ready_partial contract-only |
| Calibration / entropy / confidence | Supports abstain/retrieve/correct thresholds and high-confidence wrong detection | indexed / partially executable |
| Activation / logit interpretability | Row gradient norms, module delta norms, activation summaries, feature ablations, and activation patch recovery cards for tiny probes | ready_partial deterministic telemetry |
| State-space / selective scan / Mamba | Repo-stream compression scaffold after context/retrieval packets stabilize; actual Mamba training still closed | ready_partial deterministic compressor |
| GNN / graph message passing | Deterministic repo graph encoder/message-passing scaffold for node and graph feature packets; learned GNN training closed | ready_partial deterministic encoder |
| Denoise / diffusion | Repair trajectory for bad outputs, masked spans, verifier failures | indexed / partially executable |
| Dataset cartography / attribution | Future dataset-example dynamics and influence layer for curriculum compiler | indexed / partially executable |

### Practical Rule

Before reopening any training probe, the run card must be able to answer:

```text
what tensors entered the model
what shapes and masks they had
which logits were supervised
which losses were enabled
which gradients were produced
which optimizer/scheduler settings updated parameters
which telemetry proves the model learned or failed
```

If a run cannot answer those, it is not evidence for model intelligence. It is only an uncontrolled execution attempt.

### Current Low-Level Gaps

Stage8698 found no concept group that exists in sessions but is totally absent from recovery. The remaining low-level gaps are narrower:

- `mixed_precision_memory`: documented, but no executable memory/mixed-precision policy module yet.
- `activation_interpretability`: documented and telemetry-adjacent, but no activation cache, patching, logit-lens, or gradient-attribution module yet.
- `graph_gnn`: repo graphs exist, but no executable GNN/message-passing encoder module yet.

These should stay behind telemetry/runtime recovery. Do not build GNN/Mamba/mixed-precision training before the deterministic context packer, telemetry, and verifier loop are stable.

## Canonical Stack

| Layer | Model / module family | Primary job | Output |
| --- | --- | --- | --- |
| 1 | N-gram / Markov priors | Cheap local syntax/style transition priors | local transition prior, anomaly score |
| 2 | Encoder-only retriever | Evidence retrieval and grounding | top-k files, symbols, tests, docs |
| 3 | Cross-encoder reranker | Re-rank evidence against task/failure | evidence confidence |
| 4 | Repo graph / GNN | Import/call/test/dependency impact | binding candidates, impacted tests |
| 5 | SSM / Mamba | Long repo/log/history compression | compressed repo state |
| 6 | RNN/LSTM/GRU trace model | Tool/test/action trace state | workflow state, loop risk |
| 7 | 100M encoder-decoder seq2seq | Structured state transition policy | action labels, bounded args, repairs |
| 8 | Linear/tree/MLP heads | Gates, risk, confidence, OOD, junk ranking | continue/retrieve/correct/abstain |
| 9 | Decoder-only causal model | Bounded candidate generation only | candidate text or patch hunk |
| 10 | Denoiser / masked LM | Infill and repair failed outputs | cleaned output, repaired spans |
| 11 | Diffusion iterative repair | Multi-step verifier-guided refinement | refined candidate trajectory |
| 12 | Autoencoder compressor | State/diff/log compression and anomaly detection | latent state, reconstruction error |
| 13 | Energy / reward model | Patch quality and preference scoring | reward/energy/preference |
| 14 | Bayesian calibration | Confidence, entropy, abstention thresholds | calibrated risk interval |
| 15 | MoE / LoRA adapters | Specialist routing by language/task/repo | adapter route, specialist logits |
| 16 | RL / bandit controller | Tool/test/action selection under budget | next action policy |
| 17 | CRF / HMM sequence labeler | Structured log/code/workflow segment labels | segment labels |
| 18 | GAN/adversarial generator | Hard negatives and shortcut tests | adversarial dataset rows |
| 19 | Symbolic verifiers | Parser, AST, type, lint, tests, static checks | pass/fail, repair signal |
| 20 | World/counterfactual model | Predict consequences of possible edits | expected verifier result, risk |

## Component Placement

### Observe

Use exact tools and low-cost models before the 100M student:

```text
file tree
symbol index
AST parser
repo graph
test index
retrieval index
long-log compressor
```

Model families:

- `encoder_only_retriever`
- `state_space_mamba`
- `gnn_repo_graph`
- `ngram_markov`
- `autoencoder_compressor`

### Orient

Convert raw evidence into a typed state packet:

```text
goal
language
repo capability profile
allowed imports
evidence sufficiency
graph bindings
budget
authority state
```

Model families:

- `linear_tree_mlp_heads`
- `bayesian_calibration`
- `rnn_lstm_gru_trace`
- `crf_hmm_sequence_labeler`
- `world_model_counterfactual`

### Plan

Predict the safe software-maintenance transition:

```text
retrieve_more
copy_prior
correct_prior
build_from_import
build_from_scratch
select_verify
select_repair
abstain
```

Model families:

- `encoder_decoder_seq2seq`
- `moe_lora_adapters`
- `rl_bandit_controller`
- `gnn_repo_graph`

### Act

Only after gates pass, produce bounded output:

```text
small patch operator
bounded decoder args
targeted import choice
function/class/file skeleton
test plan
```

Model families:

- `encoder_decoder_seq2seq`
- `decoder_only_causal`
- `ngram_markov`
- `symbolic_verifiers`

### Verify

External checks dominate learned confidence:

```text
parse
AST validity
import whitelist
callable existence
unit smoke
lint/type check
leak check
grounding check
budget check
```

Model families:

- `symbolic_verifiers`
- `energy_reward_model`
- `bayesian_calibration`
- `linear_tree_mlp_heads`

### Repair

Repair should be iterative and evidence-guided:

```text
bad output
+ verifier failure
+ masked weak spans
-> repaired bounded output
```

Model families:

- `denoiser_masked_lm`
- `diffusion_iterative_repair`
- `encoder_decoder_seq2seq`
- `energy_reward_model`

### Learn

Every failure must compile into a dataset operation:

```text
add
remove
relabel
rebalance
quarantine
generate hard negative
create preference pair
change retrieval
change loss mask
```

Model families:

- `gan_adversarial_generator`
- `energy_reward_model`
- `autoencoder_compressor`
- `linear_tree_mlp_heads`
- `symbolic_verifiers`

## Fusion Contract

The effective action is not one model's raw output. It is the result of fused signals:

```text
effective_action =
  structured_head_logits
  + deterministic_budget_overlay
  + retrieval_evidence_confidence
  + repo_graph_binding_confidence
  + junk_ranker_route
  + verifier_result
  + calibrated_confidence
```

Effective decode is stricter:

```text
effective_decode_allowed =
  learned_decode_allowed
  AND deterministic_budget_ok
  AND action_allows_decode
  AND evidence_allows_decode
  AND junk_ranker_route in {KEEP_BOUNDED_DECODER, USE_FOR_DENOISE_REPAIR}
  AND structured_head_confidence_ok
```

If any hard gate fails, decode routes to retrieve, abstain, or repair instead of emitting body/source text.

## Current Implementation Boundary

Currently real evidence exists for:

- structured transition manifests
- neutralized shortcut audits
- dataset judge/gate scaffolding
- repo-state graph seed rows
- symbol-binding objective seeds
- bounded decoder dependency smoke
- finite action heads
- authority-zero recovery artifacts
- session-backed model-family recovery

Still not implemented as active model components:

- SSM/Mamba repo-state compressor
- GNN repo graph encoder
- denoising repair model
- diffusion iterative repair model
- energy/reward model
- MoE/adapter router
- RL/bandit controller
- cross-model forward-pass fusion module
- activation/SAE interpretability module

## Scale Rule

The project can scale to 1M+ examples only through judged curriculum cells.

Each added example needs:

```text
task family
structure type
input evidence
target transition
loss mask
authority state
shortcut audit
leak audit
heldout split
validator or judge result
```

Raw Python examples are not enough. They must be wrapped as state-transition examples.

## Import / Build Objective

For user intent that asks the agent to build software, the model should learn this decision:

```text
intent + allowed imports + repo state + evidence
-> use whitelisted import
OR build on top of whitelisted import
OR build from scratch
OR retrieve more
OR abstain
```

This is not free-form prose. It is a structured build-mode transition.

The decoder is used only after:

- build mode is decided without target leakage
- import whitelist is validated
- repo context is grounded
- output budget is known
- verifier route is available

## Priority Order

1. Keep central research spine and model-stack spine synchronized.
2. Finish safe state-transition objectives before reopening decoder CE.
3. Expand dataset through judged cells, not raw corpus volume.
4. Add junk/risk/confidence/OOD heads before broad decode.
5. Add repo graph encoder before claiming repo-wide understanding.
6. Add denoising/diffusion only as repair, not authority.
7. Add reward/energy after verifier results are reliable.
8. Add SSM/Mamba for long-context compression after graph/retrieval contracts are stable.
9. Add MoE/adapters only when task/language slices have reliable gates.
10. Add RL/bandit only after supervised actions are stable.

## Backup Contract

Durable copies of this spine and the recovered registry should be stored under:

```text
/arxiv/code/model_stack_spine
```

This backup must include:

- this canonical spine
- the model-family stack registry
- the recovery summary that created the registry
- a manifest with hashes


### State-Space Compressor Boundary

Stage8708 recovers `state_space_repo_state_compressor.py` as a deterministic selective-scan-style support module. It compresses repo/log/history events into a fixed-size `compressed_repo_state` packet with retrieval hints, contamination blocking, budget dropping, and deterministic state hashes.

This is not Mamba training and does not authorize long-context model execution. It is the interface layer required before any future SSM/Mamba module can be trained safely.


### Gradient/Activation Interpretability Boundary

Stage8710-8711 recover `gradient_activation_interpretability.py` as a non-executing telemetry layer. It defines row gradient norm cards, module delta norm cards, activation cache summaries, feature ablation attribution, and activation patch recovery cards.

This does not authorize model execution. It only defines what the next tiny native probe must emit so failures can be attributed to bad rows, weak features, bad representations, bad heads, loss weighting, or gradient routing.


### Mixed-Precision Runtime Boundary

Stage8712 recovers `mixed_precision_runtime_contract.py` as a contract-only policy module. It validates `fp32`, `bf16`, and `fp16` requests, estimates memory, blocks invalid GradScaler/autocast combinations, and records activation-checkpointing intent.

This does not authorize mixed-precision execution or training. It only defines the policy card future probes must satisfy before precision/memory settings can be trusted.


### Repo Graph Encoder Boundary

Stage8714-8715 recover `repo_graph_encoder.py` as a deterministic message-passing scaffold over audited repo-state graph packets. It validates endpoint resolution, blocks label-coded graph IDs, hashes node/relation features, emits node embedding hashes and graph embedding hashes, and feeds symbol binding, edit localization, patch operator, verifier repair, and bounded decoder argument objectives.

This is not learned GNN training. It is the graph-feature interface needed before any future GNN encoder can be trained safely.


### Rubric Judge Calibration Boundary

Stage8716-8717 recover `rubric_judge_calibrator.py` as a deterministic calibration layer between rubric/teacher judge signals and verifier outcomes. It emits weighted rubric scores, judge confidence, verifier disagreement, manual-review routes, quarantine routes for authority/leak risk, and a mean Brier-style calibration card.

Rubrics and LLM/teacher judges are not ground truth. High-confidence judge/verifier disagreement blocks acceptance and routes to manual review; no scoring, Gemma, model execution, runtime, training, or promotion authority is opened.


### Operator/Codelength Interface Boundary

Stage8718-8719 recover `operator_codelength_interface.py` as the operator inventory and candidate-choice measurement layer. It restores the software-maintainer operator categories, probability normalization, target NLL bits, uniform baseline bits, compression gain, regret, exact choice, and bits-per-row metrics.

Accuracy alone is not sufficient for future choice probes. Any neural selector or bounded decoder candidate-selection probe must report codelength/compression metrics before promotion. This interface is non-executing and opens no scoring, training, runtime, Gemma, or promotion authority.

## Stage8720 Forgotten Vital Module Queue

Stage8720 separates already-recovered support modules from high-value concepts that are still concept-only or contract-missing. These are not authorization gates for training; they are recovery targets that should be rebuilt before broad mining/training resumes.

Priority queue:

1. `cross_encoder_reranker_calibration` - calibrated task/evidence pair reranking after BM25/dense/hybrid retrieval.
2. `dataset_cartography_active_learning` - confidence, variability, forgetting, difficulty, hard/easy/redundant row accounting for 1M+ scale-up.
3. `training_data_attribution_influence` - helpful/harmful/nearest training row accounting for failure-to-data repair.
4. `fusion_logits_forward_pass_contract` - no-execution contract for combining structured heads, retrieval confidence, verifier signals, and decoder logits.
5. `moe_lora_adapter_router_contract` - task/language/repo specialist routing with abstain fallback.
6. `denoise_diffusion_repair_contract` - masked-span repair loop and verifier-guided remasking contract before denoise CE can reopen.
7. `adversarial_hard_negative_generator` - shortcut/proxy/leakage counterexample generator for dataset judge hardening.
8. `confidence_ood_head_contract` - head-level confidence/OOD threshold, Brier/ECE, and high-confidence-wrong gates.
9. `structured_data_operation_curriculum` - table/JSON/graph/AST/log/workflow/memory operation curriculum using state + schema + addressing + operator + validator.
10. `semantic_equivalence_metamorphic_verifier` - equivalence, property, metamorphic, and API compatibility verifier contracts.

## Stage8722 Cross-Encoder Reranker Calibration

Recovered as `ready_partial_deterministic_calibration`. This closes the Stage8720 priority-1 gap at the contract level. It does not train a learned cross-encoder; it defines deterministic task/evidence pair features, reranker probability, Brier/ECE calibration metrics, leak/locked-eval blocking, and high-confidence-wrong review routing.

Artifacts:

- `scripts/cross_encoder_reranker_calibration.py`
- `tests/test_cross_encoder_reranker_calibration.py`
- `runs/summaries/stage8721_cross_encoder_reranker_calibration_readiness.json`
- `runs/summaries/stage8722_cross_encoder_reranker_calibration_graph_attachment.json`

Next queue item: `dataset_cartography_active_learning`.

## Stage8724 Dataset Cartography Active Learning

Recovered as `ready_partial_deterministic_sampler`. This closes the Stage8720 priority-2 gap at the contract level. It computes confidence mean, confidence variability, loss mean, loss variability, forgetting events, label-review routing, easy/redundant downsampling, and hard/ambiguous neighbor-generation selection.

Artifacts:

- `scripts/dataset_cartography_active_learning.py`
- `tests/test_dataset_cartography_active_learning.py`
- `runs/summaries/stage8723_dataset_cartography_active_learning_readiness.json`
- `runs/summaries/stage8724_dataset_cartography_active_learning_graph_attachment.json`

Next queue item: `training_data_attribution_influence`.

## Stage8726 Training Data Attribution Influence

Recovered as `ready_partial_deterministic_attribution`. This closes the Stage8720 priority-3 gap at the contract level. It compares eval failures against train rows using token overlap, tag overlap, objective agreement, label agreement/conflict, source trust, label issue score, and loss metadata. It routes neighborhoods as helpful, harmful/conflicting, missing, or weak/ambiguous.

Artifacts:

- `scripts/training_data_attribution_influence.py`
- `tests/test_training_data_attribution_influence.py`
- `runs/summaries/stage8725_training_data_attribution_influence_readiness.json`
- `runs/summaries/stage8726_training_data_attribution_influence_graph_attachment.json`

Next queue item: `fusion_logits_forward_pass_contract`.

## Stage8728 Fusion Logits Forward-Pass Contract

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 priority-4 gap at the contract level. It fuses structured-head confidence, retrieval confidence/coverage, verifier pass/failure, decoder budget/schema readiness, and OOD/high-confidence-wrong signals. The fusion route is conservative: unsafe signals win over aggregate confidence.

Routes:

- `ABSTAIN_UNSAFE`
- `RETRIEVE_MORE`
- `REPAIR_STRUCTURED`
- `STRUCTURED_ONLY`
- `ALLOW_BOUNDED_DECODER_SHADOW`

Important boundary: fusion never authorizes decoder CE or model execution. It can only mark a row as decoder-shadow eligible when all green signals are present.

Artifacts:

- `scripts/fusion_logits_forward_pass_contract.py`
- `tests/test_fusion_logits_forward_pass_contract.py`
- `runs/summaries/stage8727_fusion_logits_forward_pass_contract_readiness.json`
- `runs/summaries/stage8728_fusion_logits_forward_pass_contract_graph_attachment.json`

Next queue item: `moe_lora_adapter_router_contract`.

## Stage8730 MoE/LoRA Adapter Router Contract

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 priority-5 gap at the contract level. It defines conservative shadow routing for task, language, and repo-family specialists without opening adapter training or execution.

Routes:

- `USE_BASE_SHARED`
- `ROUTE_LANGUAGE_ADAPTER_SHADOW`
- `ROUTE_TASK_ADAPTER_SHADOW`
- `ROUTE_REPO_ADAPTER_SHADOW`
- `ROUTE_COMPOSED_ADAPTER_SHADOW`
- `REQUEST_SLICE_EVIDENCE`
- `ABSTAIN_ADAPTER_ROUTE`

Hard rule: adapters are shadow hints only until slice gates are reliable. Authority, leak/locked rows, OOD, high-confidence-wrong signals, missing adapter inventory, or missing slice readiness force abstain, base/shared fallback, or slice-evidence request.

Artifacts:

- `scripts/moe_lora_adapter_router_contract.py`
- `tests/test_moe_lora_adapter_router_contract.py`
- `runs/summaries/stage8729_moe_lora_adapter_router_contract_readiness.json`
- `runs/summaries/stage8730_moe_lora_adapter_router_contract_graph_attachment.json`

Next queue item: `denoise_diffusion_repair_contract`.

## Stage8730 Denoise / Diffusion Repair Contract

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 denoise/diffusion repair gap at the contract level. It plans masked-span repair trajectories for bad outputs but does not authorize denoise CE, decoder CE, model execution, or runtime.

Routes:

- `REPAIR_INTERNAL_LEAK`
- `REPAIR_SHORT_OUTPUT`
- `REPAIR_REPETITION`
- `REPAIR_WRONG_SURFACE`
- `ABSTAIN_UNRECOVERABLE`

The contract emits mask spans, iterative repair steps, verifier-feedback remasking policy, and denoise-candidate eligibility. Authority-true rows force abstain.

Artifacts:

- `scripts/denoise_diffusion_repair_contract.py`
- `tests/test_denoise_diffusion_repair_contract.py`
- `runs/summaries/stage8729_denoise_diffusion_repair_contract_readiness.json`
- `runs/summaries/stage8730_denoise_diffusion_repair_contract_graph_attachment.json`

Next queue item: `adversarial_hard_negative_generator`.

## Stage8733 Adversarial Hard-Negative Generator

Recovered as `ready_partial_no_authority_generator`. This closes the Stage8720 adversarial hard-negative gap at the contract level. It generates audit-only negative rows for shortcut/leakage/proxy hardening. Generated rows are not training positives and all loss/model/runtime/decode authorities remain closed.

Attack types:

- `PROXY_LABEL_SWAP`
- `EVIDENCE_REMOVED`
- `LEAK_INJECTION`
- `DUPLICATE_COLLISION`
- `MISLEADING_RETRIEVAL`

Artifacts:

- `scripts/adversarial_hard_negative_generator.py`
- `tests/test_adversarial_hard_negative_generator.py`
- `runs/summaries/stage8731_adversarial_hard_negative_generator_readiness.json`
- `runs/summaries/stage8733_adversarial_hard_negative_generator_graph_attachment.json`

Next queue item: `confidence_ood_head_contract`.

## Stage8732 Denoise/Diffusion Repair Contract

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 priority-6 gap at the contract level. It defines masked-span repair planning for bad decoder outputs and verifier-guided remasking without opening denoise CE.

Routes:

- `REPAIR_INTERNAL_LEAK`
- `REPAIR_SHORT_OUTPUT`
- `REPAIR_REPETITION`
- `REPAIR_WRONG_SURFACE`
- `ABSTAIN_UNRECOVERABLE`

Hard rule: the denoise/diffusion layer is a repair-plan contract only. It may identify mask spans and repair steps, but denoise CE, decoder CE, model execution, runtime, source/body emission, Gemma, and promotion remain closed. Authority true forces abstain.

Artifacts:

- `scripts/denoise_diffusion_repair_contract.py`
- `tests/test_denoise_diffusion_repair_contract.py`
- `runs/summaries/stage8731_denoise_diffusion_repair_contract_readiness.json`
- `runs/summaries/stage8732_denoise_diffusion_repair_contract_graph_attachment.json`

Next queue item: `adversarial_hard_negative_generator`.


## Stage8734 Adversarial Hard-Negative Generator

Recovered as `ready_partial_no_authority_generator`. This closes the Stage8720 priority-7 gap at the contract level. It generates audit-only hard negatives for shortcut, leakage, duplicate, evidence, and misleading-retrieval probes.

Attack types:

- `PROXY_LABEL_SWAP`
- `EVIDENCE_REMOVED`
- `LEAK_INJECTION`
- `DUPLICATE_COLLISION`
- `MISLEADING_RETRIEVAL`

Hard rule: generated rows are adversarial negatives for dataset/ranker/audit hardening only. They carry closed authority, disabled loss masks, decode disabled, and expected guard route `BLOCK_OR_RETRIEVE`. They must never be learned as positives.

Artifacts:

- `scripts/adversarial_hard_negative_generator.py`
- `tests/test_adversarial_hard_negative_generator.py`
- `runs/summaries/stage8733_adversarial_hard_negative_generator_readiness.json`
- `runs/summaries/stage8734_adversarial_hard_negative_generator_graph_attachment.json`

Next queue item: `confidence_ood_head_contract`.

## Stage8736 Confidence/OOD Head Contract

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 priority-8 gap at the contract level while priority-7 adversarial hard negatives are handled separately. It defines the head-level confidence/OOD schema, Brier/ECE calibration card, margin/entropy thresholds, high-confidence-wrong gate, OOD retrieve route, and authority/leak blocking.

Routes:

- `ACCEPT_CALIBRATED_SHADOW`
- `ABSTAIN_LOW_CONFIDENCE`
- `RETRIEVE_OOD_OR_INSUFFICIENT`
- `REVIEW_HIGH_CONFIDENCE_WRONG`
- `BLOCK_AUTHORITY_OR_LEAK`

Hard rule: confidence can provide telemetry, review routing, retrieve routing, and shadow acceptance only. It cannot authorize source/body emission, decoder CE, runtime, training, Gemma, scoring, or promotion. High-confidence wrong predictions must route to review. OOD or insufficient evidence must route to retrieve.

Artifacts:

- `scripts/confidence_ood_head_contract.py`
- `tests/test_confidence_ood_head_contract.py`
- `runs/summaries/stage8735_confidence_ood_head_contract_readiness.json`
- `runs/summaries/stage8736_confidence_ood_head_contract_graph_attachment.json`

Next queue item: `structured_data_operation_curriculum`.

## Stage8738 Structured Data Operation Curriculum

Recovered as `ready_partial_curriculum_contract`. This closes the Stage8720 structured-data curriculum gap at the contract level. It defines typed state-transition surfaces for structures beyond raw code text.

Covered structures:

- `table`
- `json`
- `graph`
- `ast`
- `log_trace`
- `workflow`
- `memory`

Required fields for every row:

- `state`
- `schema`
- `addressing`
- `operator`
- `validator`

Boundary: this is curriculum scaffolding only. It blocks decoder CE, denoise CE, runtime reward, model execution, source/body emission, and promotion.

Artifacts:

- `scripts/structured_data_operation_curriculum.py`
- `tests/test_structured_data_operation_curriculum.py`
- `runs/summaries/stage8737_structured_data_operation_curriculum_readiness.json`
- `runs/summaries/stage8738_structured_data_operation_curriculum_graph_attachment.json`

Next queue item: `semantic_equivalence_metamorphic_verifier`.

## Stage8740 Semantic Equivalence / Metamorphic Verifier

Recovered as `ready_partial_no_execution_contract`. This closes the Stage8720 semantic verification gap at the contract level. Verification remains static contract checking only: it does not execute runtime tests, authorize scoring, or promote rows.

Verifier types:

- `semantic_equivalence`
- `property_contract`
- `metamorphic_relation`
- `api_compatibility`
- `determinism_contract`

Artifacts:

- `scripts/semantic_equivalence_metamorphic_verifier.py`
- `tests/test_semantic_equivalence_metamorphic_verifier.py`
- `runs/summaries/stage8739_semantic_equivalence_metamorphic_verifier_readiness.json`
- `runs/summaries/stage8740_semantic_equivalence_metamorphic_verifier_graph_attachment.json`

Next step: refresh the forgotten-module queue and run a support-module recovery completion audit.

## Stage8742 Source Inventory Lineage Tracker

Recovered as `ready_partial_reusable_lineage_contract`. This implements the reusable form of the Stage8663 source lineage lesson: future mined rows must carry source identity and transformation lineage before they can enter objective builders.

Required lineage fields:

- `source_id`
- `content_hash`
- `transform_chain`
- `split_eligibility`
- `lineage_hash`
- `license_status`
- `security_policy_present`

Hard rule: locked-eval sources are never train-eligible. Unknown-license train rows require review. External train rows without security-policy evidence are blocked. Missing content hash or source/body leak blocks admission.

Artifacts:

- `scripts/source_inventory_lineage_tracker.py`
- `tests/test_source_inventory_lineage_tracker.py`
- `runs/summaries/stage8741_source_inventory_lineage_tracker_readiness.json`
- `runs/summaries/stage8742_source_inventory_lineage_tracker_graph_attachment.json`

Next queue item: `source_provenance_license_security_filter`.
