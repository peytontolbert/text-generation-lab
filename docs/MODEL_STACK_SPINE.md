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

## Stage8744 Source Provenance License Security Filter

Recovered as `ready_partial_source_admission_contract`. This pairs with the source lineage tracker to decide whether a source can enter structured curriculum admission, needs review, or must be blocked.

Routes:

- `ALLOW_SOURCE_FOR_STRUCTURED`
- `ALLOW_SOURCE_FOR_HOLDOUT_ONLY`
- `HOLD_LICENSE_REVIEW`
- `HOLD_SECURITY_REVIEW`
- `BLOCK_SECRET_OR_PII`
- `BLOCK_LOCKED_EVAL_TRAIN`
- `BLOCK_DISALLOWED_IMPORT_SOURCE`
- `BLOCK_MISSING_LINEAGE`

Hard rule: source admission requires lineage, license/security metadata, allowed import provenance when imports are required, and secret/PII screening. Clean sources may become structured candidates only; this does not open decoder CE, runtime, source/body emission, training, Gemma, scoring, or promotion.

Artifacts:

- `scripts/source_provenance_license_security_filter.py`
- `tests/test_source_provenance_license_security_filter.py`
- `runs/summaries/stage8743_source_provenance_license_security_filter_readiness.json`
- `runs/summaries/stage8744_source_provenance_license_security_filter_graph_attachment.json`

Next queue item: `contamination_leakage_detector`.

## Stage8745 Support Module Recovery Completion Audit

The Stage8720 forgotten-module queue is complete at contract/scaffold level. Stage8745 audited and backed up the recovered support stack covering reranking, dataset cartography, training-data attribution, logits/forward fusion, MoE/LoRA routing, denoise/diffusion repair, adversarial hard negatives, confidence/OOD heads, structured data operation curriculum, and semantic/metamorphic verification.

Artifacts:

- `runs/summaries/stage8745_support_module_recovery_completion_audit.json`
- `runs/local/artifacts/stage8745_support_module_recovery_completion_audit/support_module_recovery_completion_cards.json`
- `/arxiv/agentkernel_recovery/stage8745_support_module_recovery_completion_audit`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, or promotion is authorized by this audit.

Next step: run a no-training support-stack integration audit over source lineage, provenance filters, queue modules, and curriculum compiler.

## Stage8747 Contamination Leakage Detector

Recovered as `ready_reusable_no_execution_gate`. This consolidates fragmented leakage checks into a reusable dataset-quality module that emits row-level contamination routes before curriculum builders, dataset rankers, or decoder objectives can consume rows.

Detected routes:

- `PASS_NO_CONTAMINATION`
- `BLOCK_TARGET_LEAK`
- `BLOCK_LABEL_CODED_ID`
- `BLOCK_HELDOUT_OVERLAP`
- `BLOCK_BODY_OR_SOURCE_LEAK`
- `REVIEW_SPLIT_OVERLAP`
- `REVIEW_SUSPICIOUS_PROXY`

Artifacts:

- `scripts/contamination_leakage_detector.py`
- `tests/test_contamination_leakage_detector.py`
- `runs/summaries/stage8746_contamination_leakage_detector_readiness.json`
- `runs/summaries/stage8747_contamination_leakage_detector_graph_attachment.json`
- `/arxiv/agentkernel_recovery/stage8746_8747_contamination_leakage_detector`

Authority remains closed: no training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next queue item: `golden_locked_eval_suite` and drift/canary regression controls.

## Stage8749 Golden Locked Eval Suite

Recovered as `ready_promotion_only_train_exclusion_contract`. This turns the Stage8672 locked benchmark packs into a reusable helper that validates promotion-only eval packs and exposes locked source IDs that all future builders must exclude from training.

Recovered locked source IDs: `5`.

Artifacts:

- `scripts/golden_locked_eval_suite.py`
- `tests/test_golden_locked_eval_suite.py`
- `runs/summaries/stage8748_golden_locked_eval_suite_readiness.json`
- `runs/summaries/stage8749_golden_locked_eval_suite_graph_attachment.json`
- `/arxiv/agentkernel_recovery/stage8748_8749_golden_locked_eval_suite`

Authority remains closed: no training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next queue item: `drift_canary_regression_monitor`.

## Stage8751 Drift Canary Regression Monitor

Recovered as `ready_promotion_blocking_contract`. This module preserves old skills by blocking promotion when canary slices regress, locked-eval leakage appears, contamination appears, or metric cards are missing.

Promotion block reasons:

- `regression_drop_exceeded`
- `below_min_score`
- `locked_eval_leakage`
- `contamination_detected`
- `missing_metric_card`

Artifacts:

- `scripts/drift_canary_regression_monitor.py`
- `tests/test_drift_canary_regression_monitor.py`
- `runs/summaries/stage8750_drift_canary_regression_monitor_readiness.json`
- `runs/summaries/stage8751_drift_canary_regression_monitor_graph_attachment.json`
- `/arxiv/agentkernel_recovery/stage8750_8751_drift_canary_regression_monitor`

Authority remains closed: no training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: support-stack integration audit over source lineage, provenance, contamination, locked eval, canaries, and curriculum compiler.

## Stage8752 Support Stack Integration Audit

Status: `integration_ready` at no-training contract level.

The curriculum compiler now structurally references the recovered gate set through `REQUIRED_RECOVERED_GATE_REFERENCES` and can require row-level `gate_status` via `--require-recovered-gates`. Missing or failed gates route rows to `NEEDS_HUMAN_REVIEW` / `human_review` instead of training objectives.

Recovered compiler gates:

- `source_inventory_lineage`
- `source_provenance`
- `contamination_leakage_detector`
- `golden_locked_eval_suite`
- `drift_canary_regression_monitor`
- `cluster_slice_near_duplicate_detector`
- `dataset_junk_ood_ranker_v1`

Stage8752 audit result: zero missing files, zero missing graph nodes, zero missing compiler references, support tests returncode `0`.

Artifacts:

- `scripts/curriculum_compiler.py`
- `tests/test_curriculum_compiler.py`
- `runs/summaries/stage8752_support_stack_integration_audit.json`
- `runs/local/artifacts/stage8752_support_stack_integration_audit/support_stack_integration_cards.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: run a scale-readiness preflight over a small no-training manifest requiring recovered gates before any mining or training resumes.

## Stage8755 Schema Drift Detector

Recovered as `ready_partial_schema_alias_gate`. This restores the Stage8058/8059 lesson that feature/schema drift can silently poison training even when labels are otherwise clean.

Routes:

- `PASS_SCHEMA_STABLE`
- `HOLD_SCHEMA_REVIEW`
- `BLOCK_SCHEMA_DRIFT`

The detector audits:

- required field presence
- forbidden field presence
- unknown fields when the schema is closed
- field type mismatches
- alias collisions
- split vocabulary validity

The curriculum compiler now includes `schema_drift_detector` in `REQUIRED_RECOVERED_GATE_REFERENCES`. Rows missing this gate pass bit are routed to `NEEDS_HUMAN_REVIEW` when `--require-recovered-gates` is enabled.

Artifacts:

- `scripts/schema_drift_detector.py`
- `tests/test_schema_drift_detector.py`
- `runs/summaries/stage8754_schema_drift_detector_readiness.json`
- `runs/summaries/stage8755_schema_drift_detector_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next queue item: `patch_minimality_complexity_meter` or `coverage_test_selection`.

## Stage8759 Patch Coverage Flaky Governance

Recovered three no-execution support gates for future patch/body/verifier objectives.

### Patch Minimality Complexity Meter

Routes:

- `PASS_PATCH_MINIMALITY`
- `HOLD_PATCH_REVIEW`
- `HOLD_PUBLIC_API_REVIEW`
- `BLOCK_OVERBROAD_PATCH`

Checks changed-line budget, files-changed budget, complexity delta, public API touches, and new dependency/import risk.

### Coverage Test Selection

Routes:

- `PASS_TARGETED_TEST_SELECTION`
- `NEEDS_BROAD_TEST_DISCOVERY`
- `HOLD_NO_CHANGESET`

Maps changed files/symbols to candidate tests using coverage maps, path-stem matches, and symbol-test metadata. It does not run tests.

### Flaky Test Detector

Routes:

- `PASS_STABLE_FAILURE`
- `PASS_STABLE_PASS`
- `HOLD_FLAKY_FAILURE`
- `HOLD_UNSTABLE_FAILURE_SIGNATURE`
- `HOLD_NO_RERUN_EVIDENCE`
- `HOLD_INSUFFICIENT_RERUNS`

Separates stable failures from flaky pass/fail mixes and unstable failure signatures using provided rerun observations only. Runtime remains closed.

Artifacts:

- `scripts/patch_minimality_complexity_meter.py`
- `scripts/coverage_test_selection.py`
- `scripts/flaky_test_detector.py`
- `runs/summaries/stage8756_patch_minimality_complexity_meter_readiness.json`
- `runs/summaries/stage8757_coverage_test_selection_readiness.json`
- `runs/summaries/stage8758_flaky_test_detector_readiness.json`
- `runs/summaries/stage8759_patch_coverage_flaky_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next queue item: `eval_trace_to_dataset_patch_loop`, then source-backed builders must emit complete `gate_status` cards.

## Stage8761 Eval Trace To Dataset Patch Loop

Recovered as `ready_partial_failure_to_curriculum_contract`. This closes the audit loop from eval failure attribution back into explicit dataset repair operations.

Dataset patch actions:

- `ADD_COUNTERFACTUAL_NEIGHBOR`
- `ADD_RETRIEVAL_NEGATIVE`
- `ADD_BOUNDARY_POSITIVE`
- `ADD_BOUNDARY_NEGATIVE`
- `RELABEL_OR_REVIEW`
- `DOWNWEIGHT_OR_PRUNE`
- `HOLDOUT_LONG_OUTPUT`
- `ADD_VERIFIER_REPAIR_ROW`
- `REQUEST_SOURCE_EVIDENCE`

Purpose: eval failures should not become vague narrative notes. They become typed patch records that the curriculum compiler, dataset judge, adversarial generator, and future source-backed builders can consume.

Artifacts:

- `scripts/eval_trace_to_dataset_patch_loop.py`
- `tests/test_eval_trace_to_dataset_patch_loop.py`
- `runs/summaries/stage8760_eval_trace_to_dataset_patch_loop_readiness.json`
- `runs/summaries/stage8761_eval_trace_to_dataset_patch_loop_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: update source-backed builders to emit full `gate_status` cards and run a no-training scale-readiness preflight before mining resumes.

## Stage8762-8764 Gate Status Contract And No-Training Preflight

Recovered as `ready_complete_recovered_gate_card_contract` plus a no-training compiler preflight. This closes the gap between recovered support modules and actual curriculum rows: future source-backed builders now have one shared `gate_status` card contract aligned to the compiler required-gate list.

Required recovered gates currently enforced by the compiler:

- `source_inventory_lineage`
- `source_provenance`
- `contamination_leakage_detector`
- `golden_locked_eval_suite`
- `drift_canary_regression_monitor`
- `cluster_slice_near_duplicate_detector`
- `dataset_junk_ood_ranker_v1`
- `schema_drift_detector`

New rule: builders must emit a complete `gate_status` dict, even for rows pending audit. Missing or failed gates route rows to `NEEDS_HUMAN_REVIEW` / `human_review` and cannot create model gradients.

Stage8763 no-training preflight proved this path:

- input rows: `5`
- gate rejected rows: `3`
- `human_review` rows: `3`
- decoder CE loss count: `0`
- denoise CE loss count: `0`
- runtime reward loss count: `0`
- authority rows: `0`
- compiler output audit: passed

Patched source-backed symbol-binding builders now import `gate_status_contract` for future reruns instead of free-handing gate cards. Existing Stage8674/8676 historical artifacts were not rewritten.

Artifacts:

- `scripts/gate_status_contract.py`
- `tests/test_gate_status_contract.py`
- `runs/summaries/stage8762_gate_status_contract_readiness.json`
- `runs/summaries/stage8763_no_training_scale_readiness_preflight.json`
- `runs/summaries/stage8764_gate_status_preflight_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: patch remaining source-backed builders to use `gate_status_contract`, then recover source-backed edit localization builder.

## Stage8765-8767 Source-Backed Edit Localization Candidate Recovery

Recovered source-backed edit localization as candidate-ready, no-training rows under the new `gate_status_contract`. This fills the next missing maintenance-cognition builder after source-backed symbol binding.

Source path:

- Neutral objective source: `runs/local/artifacts/stage8636_edit_localization_neutral_manifest/edit_localization_neutral_manifest.jsonl`
- Lineage registry: `configs/software_maintainer/source_inventory_lineage_registry_stage8663.json`
- Recovered builder: `scripts/source_backed_edit_localization_builder.py`

Stage8765 built:

- rows: `504`
- targets: `72` each for `TARGET_FILE`, `TARGET_SYMBOL`, `TARGET_CONFIG`, `TARGET_TEST`, `TARGET_ENTRYPOINT`, `RETRIEVE_MORE`, `ABSTAIN_UNBOUND`
- languages: `126` each for `python`, `typescript`, `rust`, `cpp`
- splits: `168` each for `train`, `eval`, `strict`
- complete gate_status rows: `504`
- training loss rows: `0`

Stage8766 audit passed:

- contamination blocked rows: `0`
- contamination review rows: `0`
- schema blocked rows: `0`
- schema review rows: `0`
- junk route: `KEEP_STRUCTURED` for `504` rows
- max single proxy baseline: `0.14285714285714285`
- max combo proxy baseline: `0.14285714285714285`
- semantic evidence baseline: `1.0` for allowed locality evidence

Rows remain `CANDIDATE_NEEDS_AUDIT` with no trainable losses. This is not yet compiler-ready training data because the remaining recovered gate statuses must be explicitly materialized, not inferred from narrative.

Artifacts:

- `scripts/source_backed_edit_localization_builder.py`
- `tests/test_source_backed_edit_localization_builder.py`
- `runs/summaries/stage8765_source_backed_edit_localization_candidate_manifest.json`
- `runs/summaries/stage8766_source_backed_edit_localization_candidate_audit.json`
- `runs/summaries/stage8767_source_backed_edit_localization_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: recover `source_backed_patch_operator_builder` under the same gate-status contract, then later materialize compiler-ready rows only after every recovered gate has an explicit pass card.

## Stage8768-8773 Additional No-Authority Support Modules

Recovered and reconciled several concurrent support modules after stage-number conflicts. They were renumbered forward so they do not collide with already committed Stage8758/8759 or Stage8760/8761 history.

### Eval Trace Dataset Patch Loop V2

Stage8768 adds a second, more generic no-generation compiler from eval/failure traces into auditable dataset operations. It complements the earlier typed patch-action loop by emitting operations such as `add`, `add_counterfactual`, `add_preference_pair`, `holdout`, `quarantine`, `rewrite`, `relabel`, and `route_change`. Locked/hidden eval traces and traces containing target answers are blocked.

The older Stage8760 typed API remains backward-compatible through `classify_trace` and `build_patch_card`, so committed readiness scripts still run.

### Skill Tool Registry

Stage8769 recovers a typed tool/action registry for future observe-orient-act rows. It validates:

- tool id
- action type
- permission class
- input schema
- failure modes
- explicit authority requirement for dangerous permissions

Only `read_only` and `workspace_write` passing tools are marked safe for training surfaces. Runtime, network, external write, and destructive actions remain authority-gated.

### N-Gram Repetition And Style Detectors

Stage8771 recovers static text/code ranker features:

- unigram/bigram/trigram repetition ratios
- long-line count
- trailing whitespace
- tab/odd indentation anomalies
- too-few-token checks

These are non-authority features for decoder/denoise rows and dataset junk/OOD routing.

### Memory Retrieval Evaluator

Stage8772 recovers a no-execution evaluator for retrieved memories:

- relevance
- staleness
- duplicate memory
- lineage presence
- locked/hidden contamination
- skill reuse score

Stage8773 attaches n-gram/style and memory retrieval support to the central graph.

Artifacts:

- `scripts/eval_trace_to_dataset_patch_loop.py`
- `scripts/skill_tool_registry.py`
- `scripts/ngram_repetition_style_detectors.py`
- `scripts/memory_retrieval_evaluator.py`
- `runs/summaries/stage8768_eval_trace_to_dataset_patch_loop_v2_readiness.json`
- `runs/summaries/stage8769_skill_tool_registry_readiness.json`
- `runs/summaries/stage8771_ngram_repetition_style_detectors_readiness.json`
- `runs/summaries/stage8772_memory_retrieval_evaluator_readiness.json`
- `runs/summaries/stage8773_ngram_memory_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, memory writes, tool execution, or promotion is authorized.

Next step: recover source-backed patch operator builder under `gate_status_contract`, then cost/budget scheduler if still missing.

## Stage8774-8776 Source-Backed Patch Operator Candidate Recovery

Recovered source-backed patch operator as candidate-ready, no-training rows under `gate_status_contract`. This extends the recovered maintenance-cognition chain from source-backed edit localization into patch operator selection.

Source path:

- Neutral objective source: `runs/local/artifacts/stage8638_patch_operator_neutral_manifest/patch_operator_neutral_manifest.jsonl`
- Lineage registry: `configs/software_maintainer/source_inventory_lineage_registry_stage8663.json`
- Recovered builder: `scripts/source_backed_patch_operator_builder.py`

Stage8774 built:

- rows: `864`
- operators: `72` each for `MODIFY_EXISTING_SYMBOL`, `INSERT_FUNCTION`, `REPLACE_EXPR`, `WRAP_CALL`, `ADD_IMPORT`, `ADD_TEST_CASE`, `UPDATE_CONFIG_FIELD`, `CREATE_FILE`, `BUILD_ADAPTER`, `ROLLBACK_PATCH`, `RETRIEVE_MORE`, `ABSTAIN_UNSAFE`
- languages: `216` each for `python`, `typescript`, `rust`, `cpp`
- splits: `288` each for `train`, `eval`, `strict`
- complete gate_status rows: `864`
- training loss rows: `0`

Stage8775 audit passed:

- contamination blocked rows: `0`
- contamination review rows: `0`
- schema blocked rows: `0`
- schema review rows: `0`
- junk route: `KEEP_STRUCTURED` for `864` rows
- max single proxy baseline: `0.10185185185185185`
- max combo proxy baseline: `0.18055555555555555`
- semantic evidence baseline: `1.0` for allowed operator evidence

Rows remain `CANDIDATE_NEEDS_AUDIT` with no trainable losses. They are not compiler-ready training rows until all recovered gate statuses are explicitly materialized.

Artifacts:

- `scripts/source_backed_patch_operator_builder.py`
- `tests/test_source_backed_patch_operator_builder.py`
- `runs/summaries/stage8774_source_backed_patch_operator_candidate_manifest.json`
- `runs/summaries/stage8775_source_backed_patch_operator_candidate_audit.json`
- `runs/summaries/stage8776_source_backed_patch_operator_graph_attachment.json`

Authority remains closed: no mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Next step: recover source-backed verifier-repair builder under the same gate-status contract.



## Stage8777-8785 Recovered Support Gates And Central Graph Attachments

Recovered additional support modules that are required before returning to mining or training. These modules do not authorize model execution, training, runtime, source/body emission, scoring, Gemma, controller merge, memory writes, or promotion. They are control-plane and observability components for the 100M software maintainer pipeline.

### Stage8777 Cost Budget Scheduler

Recovered `scripts/cost_budget_scheduler.py` as a no-execution budget router. It evaluates token/tool/test/diff/time budgets and returns conservative routes such as:

- `STOP_BUDGET_EXHAUSTED`
- `HOLD_BUDGET_REVIEW`
- `RETRIEVE_MORE_WITHIN_BUDGET`
- `RETRIEVE_OR_INSPECT_MORE`
- `STOP_VERIFIED_WITHIN_BUDGET`
- `CONTINUE_WITHIN_BUDGET`

Readiness metrics:

- sample rows: `3`
- budget-ok rows: `2`
- retrieve rows: `1`
- stop rows: `2`
- authority rows: `0`

### Stage8778 Static Analysis Security Scanner

Recovered `scripts/static_analysis_security_scanner.py` as a no-runtime deterministic scanner over code/config text fields. It detects high-risk patterns before rows can become decoder or repair data.

Initial risk patterns include:

- `eval` / `exec`
- `shell=True`
- `pickle.load` / `pickle.loads`
- unsafe `yaml.load`
- SQL string concatenation
- hardcoded secrets
- insecure random token generation
- `DEBUG=True`

Routes:

- `PASS_STATIC_SECURITY_SCAN`
- `HOLD_SECURITY_REVIEW`
- `BLOCK_SECURITY_RISK`

Readiness metrics:

- sample rows: `4`
- pass rows: `1`
- review rows: `1`
- blocked rows: `2`
- finding count: `3`
- authority rows: `0`

Stage8779 attached both modules to the central graph as support modules for the dataset judge, curriculum compiler, source-backed patch/operator/reviewer objectives, bounded decoder CE, and denoise repair. Graph after attachment:

- nodes: `1715`
- edges: `2452`
- authority rows: `0`

### Stage8780 Weak Supervision Label Model

Recovered `scripts/weak_supervision_label_model.py` as a deterministic shadow-only label combiner for verifier, static-analysis, golden-rule, rubric-judge, teacher, retrieval-ranker, and heuristic votes.

It emits:

- weak label
- confidence
- margin
- contributing vote list
- invalid/contaminated vote count
- review/abstain route

Routes:

- `ACCEPT_WEAK_LABEL_SHADOW`
- `HOLD_WEAK_LABEL_REVIEW`
- `ABSTAIN_NO_WEAK_LABEL`

Readiness metrics:

- sample rows: `3`
- accepted shadow rows: `1`
- review rows: `1`
- abstain rows: `1`
- authority rows: `0`

Weak labels remain shadow labels. They cannot authorize training rows by themselves.

### Stage8781 Knowledge Graph Memory Store

Recovered `scripts/knowledge_graph_memory_store.py` as a typed no-authority graph-memory scaffold. It supports durable nodes/edges, tag/text retrieval, retrieval path lookup, schema review, and contamination blocking.

Allowed node types:

- `skill`
- `source_fact`
- `tool_outcome`
- `repo_entity`
- `dataset_patch`
- `eval_trace`
- `concept`

Allowed edge types:

- `supports`
- `derived_from`
- `used_tool`
- `touches`
- `verified_by`
- `similar_to`
- `blocks`
- `supersedes`

Blocked reasons include locked/hidden eval source, contamination risk, and raw source body. Readiness metrics:

- sample rows: `3`
- sample nodes: `1`
- sample edges: `0`
- blocked rows: `1`
- review rows: `1`
- authority rows: `0`

Stage8782 attached weak supervision and typed graph memory to the central graph. Graph after attachment:

- nodes: `1718`
- edges: `2472`
- authority rows: `0`

### Stage8783 Latency Resource Observability

Recovered `scripts/latency_resource_observability.py` as passive telemetry over latency, memory, token, tool-cost, and tool-call budgets.

It produces routes:

- `PASS_RESOURCE_OBSERVABILITY`
- `HOLD_RESOURCE_BUDGET_WARNING`
- `BLOCK_RESOURCE_BUDGET_VIOLATION`

Readiness metrics:

- sample rows: `3`
- pass rows: `1`
- warning rows: `1`
- blocked rows: `1`
- budget violation rows: `1`
- authority rows: `0`

This is observability only. It does not execute tools or authorize runtime.

### Stage8784 Repository Universe Builder

Recovered `scripts/repository_universe_builder.py` as a deterministic no-authority repository-universe feature builder. It turns repository metadata summaries into hashed vectors, 3D coordinates, and k-NN repo similarity edges without including raw source.

Readiness metrics:

- sample repos: `3`
- sample edges: `3`
- vector dimension: `16`
- raw source rows: `0`
- authority rows: `0`

This module supports future `/arxiv/repositories` indexing and program-state multimodality, but it is not a mining authorization.

Stage8785 attached latency/resource observability and repository-universe features to the central graph. Graph after attachment:

- nodes: `1719`
- edges: `2492`
- authority rows: `0`

Current next best step remains: recover source-backed verifier-repair builder under `gate_status_contract`, then continue the source-backed objective chain toward bounded decoder CE only after all candidate manifests and audits are restored.


### Stage8786-8787 Traced Eval Observability

Recovered `scripts/traced_eval_observability.py` as a no-authority shared trace schema for eval harness, dataset judge, and curriculum compiler handoff.

It validates and records:

- stable trace IDs
- span trees
- metric events
- failure packets
- dataset-patch eligibility links
- contamination/locked-eval/hidden-eval/target-answer/raw-source-body blockers

Routes:

- `PASS_EVAL_TRACE`
- `PASS_FAILURE_TRACE_PACKET`
- `HOLD_TRACE_SCHEMA_REVIEW`
- `BLOCK_TRACE_CONTAMINATION`

Readiness metrics:

- sample rows: `4`
- pass trace rows: `1`
- failure packet rows: `1`
- schema review rows: `1`
- blocked rows: `1`
- dataset patch eligible rows: `1`
- authority rows: `0`

Stage8787 attached traced-eval observability to the central graph as a support module for failure attribution, dataset patch loops, cartography/active learning, curriculum compiler, bounded decoder CE, and denoise repair. Graph after attachment:

- nodes: `1719`
- edges: `2503`
- authority rows: `0`

This preserves the closed loop:

probe/eval -> traced failure packet -> attribution -> dataset patch queue -> judge/ranker -> curriculum compiler -> next closed-boundary probe.


## Stage8788-8790 Source-Backed Verifier Repair Recovery

Recovered `source_backed_verifier_repair_builder` under the same `gate_status_contract` used for source-backed symbol binding, edit localization, and patch operator.

Input source:

- Neutral verifier-repair manifest: `runs/local/artifacts/stage8643_verifier_repair_neutral_manifest/verifier_repair_neutral_manifest.jsonl`
- Source inventory lineage: `configs/software_maintainer/source_inventory_lineage_registry_stage8663.json`

Stage8788 built candidate rows:

- rows: `648`
- actions: `72` each for `DIAGNOSE_FAILURE`, `LOCALIZE_FAILURE`, `REPAIR_API_CALL`, `REPAIR_ASSERTION`, `REPAIR_IMPORT`, `REPAIR_SYNTAX`, `RERUN_VERIFIER`, `RETRIEVE_MORE`, `ROLLBACK_OR_ABSTAIN`
- languages: `162` each for `python`, `typescript`, `rust`, `cpp`
- splits: `216` each for `train`, `eval`, `strict`
- complete gate_status rows: `648`
- training loss rows: `0`

Rows are source-backed but candidate-only. They include opaque failure, patch-candidate, and verifier node IDs. They do not include raw source, raw log bodies, raw patch bodies, runtime output, target answers, decoder text, or source row IDs in model input.

Stage8789 audit passed:

- contamination blocked rows: `0`
- contamination review rows: `0`
- schema blocked rows: `0`
- schema review rows: `0`
- junk route: `KEEP_STRUCTURED` for all `648`
- gate_status complete rows: `648`
- max single proxy baseline: `0.12808641975308643`
- max combo proxy baseline: `0.1867283950617284`
- semantic evidence baseline: `1.0`

`verifier_signal` remains allowed semantic evidence. Non-evidence graph/budget/visibility proxies are below the shortcut ceiling.

Stage8790 attached source-backed verifier-repair to the central graph:

- graph nodes: `1719`
- graph edges: `2512`
- authority rows: `0`

Authority remains closed: no training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma, controller merge, or promotion is authorized.

Current next best step: recover bounded decoder argument candidate controls under `gate_status_contract`, then use those to rebuild the bounded decoder CE candidate path without bypassing loss masks or safety gates.

## Stage8791-8794 Query Expansion and Recovery Integration

Recovered `scripts/query_expansion_rewriter.py` as the last Stage8753 missing-real support module.

Its job is narrow and evidence-facing:

- generate retrieval query variants from visible intent, symbol, error, API, path, language, and test-name hints
- emit `query_variants`, `query_source_bits`, and `expansion_reason`
- block rows exposing target-coded fields such as `target_label`, `clean_state`, `target`, `answer`, or `patch_operator`
- keep retrieval execution, training, scoring, runtime, and promotion closed

Stage8791 readiness passed:

- sample rows: `3`
- query variants: `6`
- pass rows: `1`
- hold rows: `1`
- blocked rows: `1`
- leak or target rows: `1`
- authority rows: `0`

Stage8792 re-audited the Stage8753 parallel recovery list:

- audited missing-real modules: `16`
- ready local modules: `16`
- modules with missing files: `0`
- modules missing readiness summaries: `0`
- authority rows: `0`

Stage8793 attached Stage8791 query expansion readiness and Stage8792 parallel recovery completion to the central graph:

- graph nodes: `1720`
- graph edges: `2524`
- added nodes: `1`
- authority rows: `0`

Stage8794 ran a no-registry support-stack integration audit against the Stage8793 graph:

- modules reviewed: `16`
- ready local modules: `16`
- missing file modules: `0`
- missing readiness modules: `0`
- missing graph modules: `0`
- focused tests: `16`
- focused test return code: `0`
- blockers: `[]`

Current frontier:

```text
source lineage/provenance
-> contamination/leakage
-> locked eval / drift canary
-> schema / patch / coverage / flaky gates
-> eval trace / skill registry / ngram / memory
-> source-backed edit localization
-> source-backed patch operator
-> cost / security / weak supervision / graph memory
-> latency / repository universe / traced eval
-> source-backed verifier repair
-> query expansion and recovered-module integration audit
```

The next step is bounded decoder argument candidate controls under `gate_status_contract`.

Do not resume mining, training, decoder CE, denoise CE, runtime, source/body emission, scoring, Gemma comparison, controller merge, or promotion until the reconstructed registry and central spine both point at this frontier cleanly.

## Stage8796-8800 Bounded Decoder Argument Controls

Bounded decoder argument recovery has been reintroduced as a closed control objective, not as decoder CE training.

- Stage8796 built a gate-complete no-authority bounded decoder argument controls manifest from the earlier neutral Stage8645 rows.
- Stage8798 audited the controls: 504 rows, balanced labels, max proxy single 0.2857, max proxy combo 0.4286, zero training-loss rows, zero incomplete gate rows.
- Stage8799 attached the objective to the central graph as `objective:bounded_decoder_arguments` with decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion closed.
- Stage8800 reconciles the registry/spine so the current frontier is visible and does not get lost behind older recovery stages.

Current frontier:

```text
source lineage/provenance
-> contamination/leakage
-> locked eval / drift canary
-> schema / patch / coverage / flaky gates
-> eval trace / skill registry / ngram / memory
-> source-backed edit localization / patch operator / verifier repair
-> query expansion and recovered-module integration audit
-> bounded decoder argument controls
-> closed bounded decoder CE package gate
```

Do not resume mining, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, or promotion until the next bounded decoder CE package gate passes with the same recovered gate-status contract.

## Stage8801 Parallel Audit Reconciliation

The bounded decoder argument controls have two equivalent shortcut/gate audits. Both agree on 504 rows, balanced labels, max proxy single 0.2857, max proxy combo 0.4286, zero training-loss rows, and closed authority.

This means the current recovery issue is no longer argument-control schema safety. The next unresolved boundary is a closed bounded decoder CE package gate that consumes these controls without reopening CE, runtime, body emission, or scoring.

## Stage8797-8800 Bounded Decoder Argument Controls

Bounded decoder argument recovery has been reintroduced as a closed control objective, not as decoder CE training.

- Stage8797 built a gate-complete no-authority bounded decoder argument controls manifest from the earlier neutral Stage8645 rows.
- Stage8798 audited the controls: 504 rows, balanced labels, max proxy single 0.2857, max proxy combo 0.4286, zero training-loss rows, zero incomplete gate rows.
- Stage8799 attached the objective to the central graph as `objective:bounded_decoder_arguments` with decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion closed.
- Stage8800 reconciles the registry/spine so the current frontier is visible and does not get lost behind older recovery stages.

Current frontier:

```text
source lineage/provenance
-> contamination/leakage
-> locked eval / drift canary
-> schema / patch / coverage / flaky gates
-> eval trace / skill registry / ngram / memory
-> source-backed edit localization / patch operator / verifier repair
-> query expansion and recovered-module integration audit
-> bounded decoder argument controls
-> closed bounded decoder CE package gate
```

Do not resume mining, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, or promotion until the next bounded decoder CE package gate passes with the same recovered gate-status contract.

## Stage8802-8805 Closed Bounded Decoder CE Gate

The recovered bounded decoder CE path is now represented as a closed gate, not as training authority.

- Stage8802 built 504 closed CE package-gate rows from the audited argument controls.
- Stage8803 audited that zero rows have decoder CE loss enabled, zero rows are CE-eligible now, all gate-status fields are complete, and all authority remains closed.
- Stage8804 attached the gate to the central graph and introduced `objective:source_backed_decoder_target_materialization` as the next missing recovery target.
- Stage8805 updates the registry/spine frontier accordingly.

Current hard boundary: 360 rows are future CE candidates only after source-backed target text materialization. 72 are blocked for long-output/budget and 72 are blocked for retrieve-more. No decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, or promotion is authorized.

## Stage8810-8813 Output Repair Denoise Controls

Output repair/denoise is recovered as a closed control surface, not as denoise CE training.

- Stage8810 rebuilt 360 output-repair/denoise control rows from the older neutral manifest with recovered gate-status fields and all losses closed.
- Stage8811 audited shortcuts: repair signal is allowed semantic evidence, max proxy single/combo are 0.2083, and denoise CE eligible-now rows remain zero.
- Stage8812 attached the objective to the central graph and recorded `objective:verifier_guided_repair_target_materialization` as the next missing recovery target after source-backed decoder target materialization.
- Stage8813 updates the registry/spine frontier accordingly.

Current boundary: denoise can classify bad-output repair routes and future masked-repair candidates, but denoise CE, decoder CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.

## Stage8806-8809 Source-Backed Decoder Target Materialization

Recovered source-backed decoder target materialization as a closed control layer. Stage8806 materialized 360 bounded target texts into a separate target-store artifact and kept 144 rows blocked. Stage8807 audited that target text is not copied into the manifest/model input, target refs and hashes match, authority and loss rows are zero, and CE eligibility remains zero. Stage8808 attached this to the central graph.

Important blocker discovered: 120 target hashes repeat across train/eval/strict, covering all 360 target-store rows. This is not a materialization failure while CE is closed, but it blocks future CE selection until split dedup or split-specific target materialization is designed.

Current next step: build split-deduped closed CE candidate selection from the target store. Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.

## Stage8814 Transformer Path Study Index

The lab's primary tiny-model intelligence path is the recovered transformer, not the GRU scaffold. The graph now indexes `legacy_src/agentkernel_lite/modeling_transformer.py`, `legacy_src/agentkernel_lite/training_loop.py`, `tests/test_transformer_recovery.py`, and the Stage8703 low-level concept checklist as the required study/debug path.

Study/debug order:

1. Tensor shapes through config, embedding, head split/merge, encoder/decoder, and logits.
2. `nn.Linear` as matmul/projection for Q/K/V/O, MLP, LM head, retrieval heads, and structured heads.
3. Multi-head attention mechanics: QKV, RoPE, causal/padding masks, scaled-dot-product attention, merge/project out.
4. State as evolving hidden tensor plus encoder memory read by decoder cross-attention.
5. Loss/learning through decoder CE, autograd, gradient clipping, and optimizer step.

This node should be used when debugging future bounded decoder CE, denoise repair, fusion/logit contracts, activation telemetry, and structured heads. It opens no training/runtime authority.

## Stage8810-8813 Split-Deduped Closed CE Candidate Selection

Recovered split-deduped closed CE candidate selection from the source-backed target store. Stage8810 selected 120 unique target-hash candidates and blocked 384 rows. Stage8811 audited that all selected candidates are train-only, with zero eval/strict selected rows, zero loss rows, zero CE eligibility, and zero authority rows. Stage8812 attached this to the central graph.

This is useful train-side candidate support but not a probe-ready CE package. The next missing module is eval/strict unique target materialization or a heldout evaluation design that avoids cross-split target duplication.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.

## Stage8816 Split-Deduped Closed CE Candidate Selection

The source-backed target store was split-deduped into a closed CE candidate support set. This is not a probe-ready CE package.

- Stage8810 selected 120 unique train candidates and blocked 384 rows.
- Stage8811 audited the result: selected eval rows 0, selected strict rows 0, probe_ready false, decoder CE eligible-now rows 0, training loss rows 0.
- Stage8812 attached this to the graph as train-only candidate support and recorded the remaining gap: eval/strict unique target materialization or a heldout evaluation design.
- Stage8816 reconciles this branch into the registry/spine after the transformer-path index.

Next boundary: build eval/strict unique target materialization or a heldout evaluation design before any decoder CE loss-mask package. Do not open decoder CE/runtime.

## Stage8817-8819 Eval/Strict Target Gap

Split-dedup selected 120 train-only CE candidates. The remaining blocker is now explicit: 240 eval/strict rows have duplicate target hashes and cannot support a clean CE probe package.

- Stage8817 built a closed gap manifest for 120 eval and 120 strict duplicate-target rows.
- Stage8818 attached the gap to the graph with two valid resolution paths: semantically unique eval/strict target materialization, or heldout non-CE decoder evaluation design.
- Stage8819 reconciles the registry/spine and recommends heldout non-CE decoder evaluation design first unless a real unique eval/strict source is available.

Do not solve this by suffixing target text or adding split markers. That would create an artificial eval distinction and weaken the probe. CE/runtime remain closed.

## Stage8817-8819 Eval/Strict Unique Target Gap

The split-deduped CE candidate path revealed that train candidates can be selected safely, but eval/strict target hashes duplicate train target hashes. Stage8817 materialized this as 240 explicit gap rows: 120 eval and 120 strict. Stage8818 attached the gap to the graph, and Stage8819 reconciles it into the registry/spine.

Current next step: design split-unique eval/strict target materialization or a heldout non-CE evaluation package. Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.

## Stage8820-8822 Heldout Non-CE Decoder Eval Design

Heldout eval/strict decoder evaluation is now represented as a non-CE design. This avoids using duplicate eval/strict target hashes for CE scoring.

- Stage8820 built 240 eval/strict design rows with no target text, no CE loss, no runtime/Gemma/scoring, and probe_ready false.
- Stage8821 attached the design to the graph and introduced `objective:future_model_output_packet_schema` as the next missing contract.
- Stage8822 reconciles the registry/spine.

Next boundary: future model-output packet schema/telemetry must exist before any tiny probe. It should specify generated text packet fields, parse/leak/surface checks, tensor-shape/logit/loss telemetry hooks, and authority-closed evaluation metadata. CE/runtime remain closed.

## Stage8823-8825 Model Output Packet Telemetry Contract

The heldout non-CE decoder path now has an explicit future output-packet contract instead of ad hoc probe logs.

- Stage8823 built 240 eval/strict packet-contract rows requiring schema checks, leak checks, surface checks, budget checks, grounded-argument checks, locked-eval checks, cluster duplicate checks, and tensor/logit decode telemetry.
- Stage8824 attached `contract:model_output_packet_telemetry_v1` to the central graph and introduced `objective:future_probe_packet_readiness_audit`.
- Stage8825 reconciles registry/spine.

Next boundary: build a no-execution future probe packet readiness audit. It should validate packet fields/checks/telemetry and authority bits before any model probe is considered. Decoder CE, denoise CE, runtime, Gemma, scoring, source/body emission, and promotion remain closed.

## Stage8826-8827 Packet Readiness Audit

The packet telemetry contract is now audited as schema-ready, but not model-probe-ready.

- Stage8826 checked 240 packet-contract rows and found zero missing fields, zero missing checks, zero missing telemetry, zero authority openings, and zero loss openings.
- Stage8827 reconciles the audit into registry/spine.

Next boundary: build a synthetic no-execution packet validator dry run. It should validate placeholder packets against the contract before any real model output is allowed into the evaluation path.

## Stage8828-8830 Synthetic Packet Validator

The output-packet schema has now been validated with synthetic placeholder packets only.

- Stage8828 generated 240 synthetic placeholder packets and validated all required fields/checks/telemetry with zero real model outputs.
- Stage8829 attached `validator:synthetic_packet_validator_dry_run_v1` to the graph and introduced `objective:authority_closed_model_output_capture_preflight`.
- Stage8830 reconciles registry/spine.

Next boundary: design an authority-closed model-output capture preflight. It should specify how future model outputs would be captured into validated packets, but still must not run the model or open decoder CE/runtime/Gemma/scoring.

## Stage8831-8833 Authority-Closed Model Output Capture Preflight

The next decoder-eval boundary is now a design-only capture preflight, not a model run.

- Stage8831 built 240 authority-closed capture-preflight rows from synthetic placeholder packets: zero model outputs, zero artifact writes, zero loss openings, and zero execution authority.
- Stage8832 attached the capture preflight to the graph and introduced `objective:model_output_capture_preflight_audit`.
- Stage8833 reconciles registry/spine.

Next boundary: audit the capture preflight design. Only after that should a future runner design be considered, and even then it must remain behind explicit model-execution and CE authority gates.

## Stage8834-8836 Capture Preflight Audit

The model-output capture preflight has now passed a closed-authority audit.

- Stage8834 audited 240 preflight rows: zero execution-allowed rows, zero model-output rows, zero artifact-write rows, zero authority openings, and zero loss openings.
- Stage8835 attached the audit to the graph and introduced `objective:future_model_output_capture_runner_static_design`.
- Stage8836 reconciles registry/spine.

Next boundary: static runner-interface design only. This should specify CLI flags/artifact paths/assertions for a future capture runner, but still must not run the model or open decoder CE/runtime/Gemma/scoring.

## Stage8831-8834 Authority-Closed Model Output Capture Preflight

The future model-output capture path now has a preflight design and a static closed gate, but still no model execution.

- Stage8831 built 240 capture-preflight design rows from synthetic placeholder packets.
- Stage8832 attached `design:authority_closed_model_output_capture_preflight_v1` to the graph and introduced `objective:static_capture_preflight_gate_audit`.
- Stage8833 validated all 240 rows through the static gate with zero model-output, probe-ready, model-execution, decoder-CE, authority, or loss openings.
- Stage8834 reconciles registry/spine.

Next boundary: recover an authority-ticket schema for future model-output capture. It must describe the exact authorization fields needed before checkpoint loading or model forward/decode can ever be considered.

## Stage8837-8839 Future Runner Static Design

The future model-output capture runner now has a static interface design, but still no runnable model path.

- Stage8837 defined required CLI flags, artifact paths, and assertions for a future runner. All 240 rows keep checkpoint loading, model forward, decode, CE, runtime, Gemma, scoring, and artifact writes closed.
- Stage8838 attached `design:future_model_output_capture_runner_static_v1` to the graph and introduced `objective:future_model_output_capture_authority_ticket_schema`.
- Stage8839 reconciles registry/spine and restores latest-stage metrics after the concurrent Stage8834-8836 path.

Next boundary: recover the authority-ticket schema. This ticket must define the exact explicit authorization fields required before any future checkpoint load, forward pass, decode, output artifact write, CE, runtime, Gemma, or scoring path can open.

## Stage8840-8843 Authority Ticket Schema

The future model-output capture path now has a closed-by-default authority-ticket schema.

- Stage8840 created 240 ticket-schema rows with all gated operations denied by default: checkpoint load, forward, decode, model-output artifact write, decoder CE, denoise CE, runtime, Gemma, scoring, source/body emission, and promotion.
- Stage8841 attached `schema:model_output_capture_authority_ticket_v1` to the graph.
- Stage8842 audited all 240 rows: zero allowed-operation rows, zero opening rows, zero authority openings, and zero missing denials.
- Stage8843 reconciles registry/spine.

Next boundary: recover a closed ticket-instance dry run. That dry run should instantiate denied tickets and prove the runner would reject them before any future execution path is considered.

## Stage8844 Special Token Recovery Contract

The special-token contract has been recovered from preserved `/arxiv` tokenizer artifacts and folded back into the training spine.

- Stage8844 records the recovered 100M tokenizer as `agentkernel_bytelevel_bpe_v1` with vocab size `1506`.
- PAD/BOS/EOS/UNK are fixed as `<pad>/<s></s>/<unk>` with IDs `0/1/2/3`.
- The tokenizer contains 150 added special tokens, including 146 AgentKernel structural `<AK_...>` tokens and 24 copy-source slot tokens.
- The full inventory and semantic grouping are now in `configs/tokenizer/agentkernel_special_token_contract_stage8844.json`.
- The durable note is `docs/SPECIAL_TOKEN_RECOVERY_CONTRACT_STAGE8844.md`.

Recovered control rule:

`<AK_...>` tokens are structural/control vocabulary, not ordinary user-facing prose. They may appear only in authorized structured/control surfaces. Legacy internal-control families such as `<MTC...>`, `<COPY...>`, `<SEM...>`, `<CTRL...>`, `<PLAN...>`, `<MNSB...>`, `<PYPLAN...>`, `POLICY_*`, `CONTROL_*`, `INTERNAL_*`, and `decoder_control` must route to denoise/negative/quarantine unless a specialized objective explicitly authorizes them.

Training boundary:

- Full 100M training must use the recovered 1506-vocab tokenizer, not the byte fallback.
- Bounded decoder CE must hard-check tokenizer hashes, vocab size, token IDs, target length, token leaks, loss masks, and route authorization.
- Zero internal-token leakage is insufficient by itself; decoder probes must also prove contentful output, non-junk length, non-repetition, and sane EOS behavior.

Next boundary: unify token guards across dataset judge, loss-mask compiler, trainer preflight, packet telemetry, and denoise routing. Then build tokenizer-ID suppression masks from the recovered tokenizer instead of relying only on string regex checks.

## Stage8844-8846 Learning Signal Improvement Contract

The learning-signal recovery is now represented as a contract rather than loose advice.

- Stage8844 created contract rows for structured/policy targets: needs_verification, retrieval_coverage, ood_query, build_mode, patch_operator, edit_localization, symbol_binding, and verifier_repair.
- The contract requires counterfactual siblings, row-field logits/losses, confusion matrices, margin/confidence/entropy, high-confidence wrong rows, token loss maps, per-row/per-module gradient norms, typed serialization, and explicit loss weighting.
- Stage8845 attached the contract to the graph and linked it to `training_data.py`, `training_loop.py`, `training_telemetry_metrics.py`, and `modeling_transformer.py`.
- Stage8846 reconciles registry/spine.

Next boundary: recover the dataset/trainer implementation plan. It should list exact code changes and gates, but still must not authorize training or decoder CE.

## Stage8847 Software Maintainer Custom Token Gap Audit

The recovered 1506-vocab tokenizer is checkpoint-compatible and strong for AgentKernel control/evidence/retrieval, but it is not yet a complete software-maintenance token vocabulary.

Recovered strength:

- 146 AgentKernel structural `<AK_...>` tokens
- 24 copy-source slot tokens
- high-level software-maintenance seed tokens: `<AK_RET_CODE>`, `<AK_ARTIFACT_REPAIR>`, `<AK_SOURCE_INSPECT>`, `<AK_PATCH_BUILD>`, `<AK_SAFE_STOP>`, `<AK_SOURCE_SLOTS>`

Gap:

The tokenizer lacks dedicated repo-state and edit-state markers such as repo, file, symbol, import, callsite, test, config, dependency, AST, graph edge, failure log, stack trace, verifier result, diff, patch, edit operator, build mode, allowed import, and blocked import.

Decision:

Do not expand the tokenizer casually. The recovered 1506-vocab tokenizer remains canonical for checkpoint-compatible 100M recovery. Repo-state learning should continue through structured tensors, manifest fields, graph node/edge typed IDs, action labels, and loss masks. Token expansion requires a separate v2 tokenizer migration with embedding/head resize, hash gate updates, token-ID suppression mask rebuild, and compatibility probes.

Next boundary: design unified special-token guards and tokenizer-ID suppression masks without expanding the tokenizer. Keep model execution and decoder CE closed.

## Stage8847-8850 Learning Signal Dataset/Trainer Implementation Plan

The learning-signal contract now has a file-specific dataset/trainer implementation plan.

- Stage8847 created six implementation-plan rows: typed input serialization, counterfactual sibling manifest gate, structured-head telemetry, gradient/loss-weight telemetry, telemetry helper expansion, and structured-head target mapping.
- Stage8848 attached the plan to the graph and linked it to `training_data.py`, `training_loop.py`, `training_telemetry_metrics.py`, and `modeling_transformer.py`.
- Stage8849 audited the plan: all required plan IDs and files are present, all rows have planned changes and acceptance checks, and training/decoder CE remain closed.
- Stage8850 reconciles registry/spine.

Next boundary: recover a code-patch readiness checklist. It should define the exact preconditions before modifying training/data code, but still must not authorize training or decoder CE.

## Stage8851-8854 Learning Signal Code Patch Readiness

The learning-signal implementation plan now has a code-patch readiness checklist, but no code patch, training, or decoder CE is authorized.

- Stage8851 recovered five checklist rows: tests-first contract, training-data patch readiness, training-loop telemetry readiness, telemetry-helper readiness, and transformer mapping readiness.
- Stage8852 attached the checklist to the central graph as `checklist:learning_signal_code_patch_readiness_v1`.
- Stage8853 audited the checklist: all global preflights, patch-order steps, required checks, and plan coverage are present; all authority and loss masks remain closed.
- Stage8854 reconciles registry/spine.

Next boundary: recover a tests-only patch plan before editing implementation files. Decoder CE, model execution, runtime, source/body emission, Gemma, scoring, and promotion remain closed.

## Stage8855 Commit Learning Signal Contract

Commit mining is now represented as a contract, not an open mining job.

- Source unit is not `commit`; it is `causal_edit_unit` derived from file clusters, symbol clusters, hunk groups, or test-code pairs.
- Hunk relevance must classify edits as `core`, `supporting`, `incidental`, or `noise`.
- Small commits may provide bounded decoder candidates only after structured labels and gates pass.
- Medium commits require segmentation before use.
- Large commits are primarily retrieval, graph, verifier, and decomposition signal; raw large-patch decoder targets remain blocked.
- Every unit must carry source provenance, contamination status, locked-eval exclusion, gate status, and junk/OOD route.

No `/arxiv/repositories` walk, commit mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, or promotion is authorized by this contract.

## Stage8859-8861 Commit Learning Signal Graph And No-Mining Gate

The commit-learning-signal contract is now attached to the central graph and gated as no-mining.

- Stage8859 attached `contract:commit_learning_signal_v1` to the graph and linked it to source lineage, provenance, contamination, locked-eval, cluster/near-duplicate, and junk/OOD gates.
- Stage8860 audited all 10 contract rows: route is `CONTRACT_ONLY_NO_MINING`, anti-cheat openings are false, source gate requirements are present, large-commit decoder targets remain blocked, and all authority/loss masks are closed.
- Stage8861 reconciles registry/spine.

Next boundary: recover a dry-run commit inventory design. It may define how to inspect repository metadata later, but it still must not walk `/arxiv/repositories`, read commits, emit training rows, train, or open decoder CE.

## Stage8865-8868 Commit Inventory Dry-Run Design

The commit inventory gap is filled as a dry-run design only.

- Stage8865 defines inventory fields, commit metadata fields, caps, and source gates.
- Stage8866 audits that the design is zero-walk, zero-commit-read, zero-diff-body, zero-patch-body, and zero-training-row.
- Stage8867 attaches the design to the graph and creates `objective:future_commit_inventory_preflight` as the next missing target.
- Stage8868 reconciles registry/spine.

Repository walking, commit reads, mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, and promotion remain closed.

## Stage8869-8871 Stale Graph Status Reconciliation

Stale graph statuses were reconciled so completed objectives no longer appear as missing.

- Stage8869 patched 8 stale missing nodes to `resolved_by_reconciled_stage`.
- Stage8870 reran the graph gap walk and preserved only true unresolved blockers.
- Stage8871 reconciles registry/spine.

Current priority: future commit inventory preflight only if repository walking is explicitly requested; otherwise verifier-guided repair target materialization controls.

## Stage8872-8875 Verifier-Guided Repair Target Materialization

Verifier-guided repair target materialization is now recovered as a closed-boundary target-store control.

- Stage8872 materializes repair targets from audited source-backed verifier-repair rows into a separate target store.
- Stage8873 audits target refs, hashes, leakage, authority, and closed denoise/runtime gates.
- Stage8874 attaches the resolved objective to the central graph.
- Stage8875 reconciles registry/spine.

This does not authorize denoise CE, runtime verifier execution, decoder CE, model execution, source/body emission, Gemma, harness, scoring, mining, or promotion.

## Stage8876-8878 Post Target Materialization Gap Reconciliation

After verifier-guided repair target controls, stale heldout eval, packet telemetry, packet readiness, and runner static-design blockers were reconciled.

Remaining blockers are closed authority gates or optional metadata-only commit inventory preflight. No training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, mining, or promotion is authorized.

## Stage8879-8881 Final Closed-Gate Recovery Walk

Bounded decoder CE and denoise repair are now reconciled as recovered closed gates rather than missing prerequisite nodes.

- Bounded decoder CE has target controls, heldout non-CE eval controls, closed package gate, and telemetry artifact gate recovered. It still requires explicit tiny execution authorization before any run.
- Denoise repair has output-repair controls, verifier-guided repair targets, and denoise/diffusion contract recovered. Denoise CE and runtime verifier execution remain closed.
- The only missing node left by the recovered graph is optional metadata-only commit inventory preflight, which must not run repository walking unless explicitly requested.

This remains no-authority recovery: no model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, mining, controller merge, memory writes, or promotion is authorized.

## Stage8882-8885 Authorization Review Cards

Three requested next-step review/design artifacts are recovered and indexed.

- Stage8882 reviews the future Stage8890 tiny structured-policy probe plan. It passes but does not run or authorize execution by itself.
- Stage8883 designs optional metadata-only commit inventory preflight with zero repository walks, zero commit reads, zero diff body reads, and zero training rows.
- Stage8884 reviews denoise authorization prerequisites as no-execution/no-CE only. Denoise CE and runtime verifier execution remain closed.
- Stage8885 reconciles these into registry/spine.

No model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, controller merge, mining, memory writes, or promotion is authorized.

## Stage8886-8888 Inactive Stage8890 Ticket

Stage8886 created a draft inactive authority ticket for the future Stage8890 tiny structured-policy probe. Stage8887 audited it and required it to remain commandless, non-executing, structured-aux only, and guarded by the Stage8862 interpretability artifact contract. Stage8888 reconciles the ticket into the registry/spine.

This does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion. Stage8890 is reserved for a future explicit one-run authorization decision.

## Stage8889 Metadata Inventory Inactive Ticket

Stage8889 closes the optional metadata-only commit inventory branch as a draft inactive ticket. It performs no repository walk, no commit read, no diff/patch/source body read, no mining, and no training row emission. Future metadata inventory would require a separate explicit ticket with caps.

## Stage8891 No-Execution Control-Plane Regression Audit

Stage8891 records that the recovered authority tickets, metadata-inventory ticket, native probe preflight, cleanup guard, and authority-ticket schema are covered by regression tests. It keeps Stage8890 reserved and opens no execution/training authority.

## Stage8892 Next Steps Decision Matrix

Stage8892 records the post-regression-audit branch decision. Without explicit future authorization, only no-execution hardening/documentation is available. Stage8890 remains a reserved tiny structured-policy probe candidate, not a live run.

## Stage8892 No-Execution Telemetry Gate Matrix

Stage8893 verifies concrete regression markers across the no-execution telemetry/gate matrix: curriculum compiler loss masks, native probe preflight, packet telemetry, capture preflight, bounded decoder CE, source-backed target materialization, output-repair denoise controls, verifier-guided repair targets, and inactive authority tickets.

This is hardening only. It opens no execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.

## Stage8893 No-Execution Telemetry Gate Matrix

Stage8893 verifies concrete regression markers across the no-execution telemetry/gate matrix: curriculum compiler loss masks, native probe preflight, packet telemetry, capture preflight, bounded decoder CE, source-backed target materialization, output-repair denoise controls, verifier-guided repair targets, and inactive authority tickets.

This is hardening only. It opens no execution, training, decoder CE, denoise CE, runtime, mining, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion.
