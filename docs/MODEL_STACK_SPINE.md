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
| Mixed precision / memory | Needed for efficient training, but currently documented-not-executable; do not depend on it for correctness yet | documented-not-executable |
| Calibration / entropy / confidence | Supports abstain/retrieve/correct thresholds and high-confidence wrong detection | indexed / partially executable |
| Activation / logit interpretability | Needed for activation cache/probe/logit-lens work; currently documented-not-executable beyond telemetry metrics | documented-not-executable |
| State-space / selective scan / Mamba | Future repo-stream compressor after context/retrieval packets stabilize | indexed concept, executable compressor still missing |
| GNN / graph message passing | Future learned repo-graph encoder; graph substrate exists, executable GNN encoder still missing | documented-not-executable |
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

