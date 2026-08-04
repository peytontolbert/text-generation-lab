# Maintainer 100M Training Stage Structure

This document converts the stage-theory notes in `training_stages.md` into a
project-specific training structure for the 100M software-maintainer model.

It is a design artifact, not training authorization. Current stage gates still
control when ledger updates, row admission, training admission, eval admission,
runtime, VM/replay, Level-3 materialization, and GPU use may occur.

## Current Authority State

This document does not change current project authority. Until separate staged
admission artifacts say otherwise, these fields remain false:

- implementation_ready
- stage12595_allowed
- replay_trustworthy
- level_3_materialized
- dataset_rows_admitted
- training_admission_allowed
- training_allowed
- strict_eval_admitted
- sealed_eval_admitted
- gpu_use_allowed

The next dataset-spine gate remains separate from this design note. As of the
latest audited state, Stage12637 authorized only Stage12638 authoritative ledger
update materialization, not row admission, training admission, replay execution,
Level-3 materialization, eval admission, or GPU use.

## Core Thesis

The 100M model should not be trained as a monolithic mix of repository text,
tool traces, patches, and verifier outcomes.

The model should be trained as a staged maintainer controller:

```text
repo/code knowledge
-> structured repo state
-> maintainer action policy
-> long-horizon state transitions
-> repo graph and symbol binding
-> edit localization
-> patch operator arguments
-> verifier-conditioned repair
-> bounded decoder
-> denoise repair
-> controlled harness iteration
-> stage-compiled distillation
```

The decoder is a bounded action inside the maintainer loop. It is not the
central authority.

## Stage Design Principles

1. Train prerequisite representations before behavior.
   A model must understand code, tests, repository layout, evidence roles, and
   symbols before it can reliably choose maintainer actions.

2. Separate objectives when their gradients encode different decisions.
   `next_action`, `continue_or_stop`, `candidate_selection`,
   `verifier_transition`, localization, and patch synthesis should not be
   collapsed until measurements show they do not interfere.

3. Train ranking only after alternatives exist.
   Candidate ranking requires pre-outcome candidate sets, near-miss negatives,
   and counterfactuals. It should not be inferred from single successful traces.

4. Delay raw code emission.
   Decoder CE should be late, localized, budget-clean, and conditioned on
   selected action, target span, operator choice, verifier state, and output
   bounds.

5. Preserve earlier competencies during later narrow stages.
   Every later patch/repair/codegen stage should include replay from structured
   policy, stop/continue, evidence sufficiency, verifier interpretation, and
   localization.

6. Treat RLVR as discovery, not foundation.
   Verifiable RL should be late and narrow, after the model can already produce
   valid actions and after verifier false-positive and reward-hacking risks are
   bounded.

7. Use stage compilation deliberately.
   If iterative loops discover good trajectories, distill the verified behavior
   into the 100M model with supervised/listwise data instead of expecting the
   100M model to discover every strategy directly.

## Stage Ledger Template

Every future training stage should have an auditable ledger entry before any
training run is admitted:

- stage_id
- parent_checkpoint
- objective
- trainable_params
- optimizer_and_context
- data_source
- supervision_source
- loss_and_masks
- auxiliary_models_or_judges
- evaluator
- acceptance_thresholds
- stop_rule
- known_risks
- protected_replay_sets
- heldout_retention_sets
- admission_decision

A new stage boundary is justified only when the data, objective, supervision,
trainable parameters, optimizer/context, auxiliary model, or evaluator changes
enough to change the meaning of the gradient. Otherwise it should be a mixture
or replay slice within an existing stage, not a new stage.

No stage is accepted for loss improvement alone. It must add measurable
information about expert maintainer behavior, such as structural labels,
evidence ranking, counterfactual flips, bounded choices, verified outcomes,
process labels, hard negatives, or replay retention.

## Canonical Stage Order

The practical order is:

1. schema/judge/control plane
2. intent/build strategy
3. repo graph and retrieval grounding
4. symbol binding
5. edit localization
6. root-cause/failure classification
7. patch operator selection
8. bounded decoder argument/rendering
9. verifier expectation
10. verifier failure to repair/denoise/abstain/retrieve
11. iterative hard-negative and verified replay
12. stage-compiled distillation

This order is stricter than generic codegen. The model should first learn the
maintainer transition system, then learn bounded patch rendering, then learn
judged scale-up. Raw free-form code generation is not the organizing principle.

## Proposed Capability Stages

### 1. Repo And Code Knowledge

Purpose:
Build latent code/repository representations.

Primary signal:
Curated repository text, docs, tests, configs, build files, issue/PR metadata,
small diffs, and compact verifier/test summaries.

Train:
- syntax and API regularities
- test and build conventions
- repo layout
- doc-code-test relationships
- issue language and maintenance vocabulary

Avoid:
- heavy chat formatting
- raw long patches as unstructured targets
- verifier rewards
- on-policy generated data

Primary transfer metrics:
- code/doc/test perplexity
- symbol reference prediction
- test-file association
- repository metadata classification
- old-language retention

### 2. Structured Repo State

Purpose:
Teach the model to represent a maintenance situation before choosing actions.

Primary signal:
State packets with request, observed evidence, repo context, file/symbol/test
summaries, verifier status, and explicit evidence sufficiency labels.

Train:
- task intent
- evidence roles
- failing signal interpretation
- missing-evidence detection
- state compression

Avoid:
- patch emission
- final-answer optimization
- hidden target labels that make the state task trivial

Primary transfer metrics:
- evidence sufficiency accuracy
- failing-signal classification
- missing-context routing
- shortcut audit pass rate

### 3. Maintainer Action Policy

Purpose:
Teach the controller action vocabulary before generating code.

Primary signal:
Structured labels such as:

```text
RETRIEVE
PLAN
LOCALIZE
PATCH
VERIFY
REPAIR
STOP
ABSTAIN
```

Train:
- next action
- continue/stop
- retrieve-more versus patch-now
- verifier-next-step
- abstention on insufficient evidence

Avoid:
- mixing all action labels into a single text-only target too early
- letting marker strings, counts, graph IDs, or hidden row fields solve the task

Primary transfer metrics:
- next-action accuracy
- stop/continue calibration
- abstention precision
- evidence-sufficiency conditioned action accuracy

### 4. Long-Horizon State Transitions

Purpose:
Make long-horizon behavior live in state prediction, not only in final text.

Primary signal:
Sequences of:

```text
request -> state_t -> action_t -> observation_t+1 -> state_t+1
```

Train:
- next-state prediction
- action consequence prediction
- progress tracking
- when to continue versus stop
- recovery from failed actions

Avoid:
- requiring verbose hidden reasoning as the deployment behavior
- optimizing only final patch success without step provenance

Primary transfer metrics:
- transition prediction accuracy
- horizon consistency
- provenance completeness
- false stop and false continue rates

### 5. Repo Graph And Symbol Binding

Purpose:
Ground the model in files, symbols, definitions, references, imports, tests, and
call edges.

Primary signal:
Graph-grounded candidate sets with positive and near-miss negative bindings.

Train:
- file candidate selection
- symbol binding
- relevant test binding
- import/call/reference relation use
- graph-conditioned retrieval

Avoid:
- graph-degree shortcuts
- stable ID leakage
- target-only path cues
- ranking before causal candidate sets exist

Primary transfer metrics:
- file recall@k
- symbol recall@k
- test association accuracy
- graph shortcut audit pass rate
- unseen-repo binding accuracy

### 6. Edit Localization

Purpose:
Locate the edit surface before synthesizing the patch.

Primary signal:
File/span candidates, evidence-bearing snippets, failing tests, near-miss spans,
and insufficient-evidence examples.

Train:
- file localization
- span localization
- evidence-present versus evidence-sufficient judgment
- retrieve-more routing

Avoid:
- direct patch text as the only supervision
- spans that can be solved by path name alone

Primary transfer metrics:
- file top-k localization
- span IoU or token overlap
- near-miss discrimination
- retrieve-more calibration

### 7. Patch Operator Arguments

Purpose:
Train constrained edit intent before raw code generation.

Primary signal:
Patch operator schemas:

```text
replace_span
insert_import
rename_symbol
adjust_call
update_test
delete_dead_branch
change_config
```

Train:
- operator choice
- operator arguments
- minimality
- dependency-aware edit intent
- patch risk classification

Avoid:
- unrestricted code emission
- overlarge patch incentives
- conflating operator selection with byte-level generation

Primary transfer metrics:
- operator accuracy
- argument validity
- patch minimality proxy
- regression-risk prediction

### 8. Verifier-Conditioned Repair

Purpose:
Teach the model to use compiler/test/type/lint outcomes as state updates.

Primary signal:
Verifier summaries, failure categories, responsible symbols/spans, and next
repair actions.

Train:
- failure diagnosis
- responsible span/symbol selection
- repair-next-action
- verifier false-positive awareness
- when to rollback or abstain

Avoid:
- reward hacking
- training on raw logs with private or unstable content
- treating verifier pass as Level-3 or training admission

Primary transfer metrics:
- failure-category accuracy
- responsible-span accuracy
- repair action accuracy
- verifier false-positive sensitivity
- rollback/abstain calibration

### 9. Bounded Decoder

Purpose:
Fill localized patch arguments after the controller has selected the edit.

Primary signal:
Budget-clean localized patch spans with loss masks, source/target hash pins,
and generation telemetry.

Train:
- bounded code emission
- argument text completion
- localized diff generation
- test-aware minimal edits

Avoid:
- long unbounded targets
- target leakage
- hidden references
- letting decoder output authorize actions

Primary transfer metrics:
- contentful output rate
- exact or semantic patch match
- short/junk/repetition rate
- internal leak rate
- bounded budget adherence

### 10. Denoise Repair

Purpose:
Improve robustness after bounded decode introduces realistic errors.

Primary signal:
Corrupted states, malformed patches, partial diffs, noisy verifier traces, and
model-generated failure cases with verified repairs.

Train:
- malformed patch recovery
- noisy evidence repair
- verifier-conditioned correction
- partial-output completion

Avoid:
- vague regeneration
- training denoise before bounded decoder errors are known
- self-generated data without external verification

Primary transfer metrics:
- corruption recovery rate
- verifier-conditioned repair accuracy
- regression on clean bounded decoder rows
- repetition and junk suppression without empty outputs

### 11. Preference And RLVR

Purpose:
Select and discover better maintainer strategies after the supervised policy is
competent.

Primary signal:
Preference pairs, verifier outcomes, on-policy attempts near the current
capability boundary, and high-quality rejection-sampled trajectories.

Train:
- patch preference
- minimality
- safe abstention
- test choice
- exploration under verifier reward

Avoid:
- early RL before valid action emission
- broad reward maximization that favors overlarge patches
- preference/RL conflict without KL and regression controls

Primary transfer metrics:
- preference win rate
- repair success rate
- patch minimality
- reward-hacking audit
- old-task retention
- unseen-repo transfer

### 12. Controlled Harness Iteration

Purpose:
Use model-dependent failures to create new information.

Primary loop:

```text
generate -> verify -> classify failure -> add targeted data -> retrain
```

Train:
- current-boundary failures
- verifier-filtered improvements
- deployment-like tool sequencing
- recovery from model-specific mistakes

Avoid:
- ungrounded self-training
- narrowing diversity to the model's own style
- mixing stale and on-policy data without labels

Primary transfer metrics:
- failure bucket reduction
- verifier pass with low false positives
- old-task retention
- standalone versus product-harness gap
- unseen-repo transfer

### 13. Stage-Compiled Distillation

Purpose:
Compress the useful behavior discovered by multi-stage loops back into a clean
100M policy.

Primary signal:
Verified trajectories, ranked candidates, process labels, failure repairs, and
high-confidence distilled demonstrations.

Train:
- clean supervised/listwise policy
- compact action control
- verifier-aware repair patterns
- stable deployment behavior

Avoid:
- treating distillation as discovery
- distilling unverified model outputs
- removing replay that protects earlier competencies

Primary transfer metrics:
- retained gains from iterative stages
- reduced regression
- smaller inference/control cost
- stable action distribution

## What To Mix Versus Separate

Likely safe to mix lightly:
- repo/code CE with small corruption repair
- structured state labels with evidence-sufficiency labels
- action policy replay with later localization/operator stages
- old capability replay in every later stage

Keep separate until measured:
- code CE and chat/instruction SFT
- denoise reconstruction and patch minimality
- process labels and final answer generation
- preference optimization and RLVR
- decoder CE and controller/action authorization
- ranking and single-trajectory imitation

Collapse only when:
- the later data is static and not model-dependent
- gradient conflict is low
- stage-specific metrics do not regress
- shortcut audits stay clean
- the merged objective preserves the information in both signals

Keep stages separate when:
- data is on-policy or model-dependent
- labels are verifier-generated or failure-mined
- the objective changes from representation to action selection
- the evaluator changes from static labels to execution outcomes
- attribution would become unclear after mixing

## Stage-Transfer Matrix

Every future training stage should report deltas on this capability vector:

```text
M(theta) =
  repo/code knowledge
  evidence sufficiency
  next action
  continue/stop
  file localization
  symbol binding
  test binding
  patch operator
  verifier transition
  bounded decode quality
  denoise recovery
  patch minimality
  regression avoidance
  old-task retention
  unseen-repo transfer
```

A stage should be considered useful only when it improves its target columns
without unacceptable regression in protected columns.

Shortcut baselines must travel with this matrix:
- metadata-only
- graph-degree-only
- surface-marker-only
- label-ID-only
- duplicate-key
- target-text leakage
- train/test source leakage
- hidden outcome leakage

## Replay, Retention, And Stop Rules

Every new stage must include frozen old-task replay and held-out retention evals.
A gain is invalid if it erases prior capability beyond threshold, increases
high-confidence wrong accepts, collapses retrieve/abstain behavior, or only wins
against one evaluator implementation.

Continue a stage only while marginal robust utility is positive:
- held-out target gain remains positive
- unseen-repo transfer improves or stays neutral
- protected retention stays within threshold
- shortcut baselines remain below threshold
- evaluator-swap performance survives
- leakage audits remain clean
- cost and operational risk stay acceptable

Stop, roll back, or redesign the stage when the measured gain is narrower than
the regression it introduces.

## Future Ablation

When training is separately admitted, the staged-controller curriculum should be
measured against a monolithic baseline that mixes repository text, traces,
patches, and verifier outcomes directly. The ablation is future evaluation
design only; it does not authorize dataset admission, training, eval, replay, or
GPU use.

The staged curriculum should beat the monolithic baseline on transfer and
retention, not just on aggregate loss. Required comparison axes include unseen
repo transfer, symbol binding, edit localization, patch minimality, verifier
repair, abstain/retrieve calibration, regression rate, and shortcut resistance.

## Practical Ordering For 100M

Recommended future training order:

```text
1. repo/code CE and compact maintenance text
2. structured repo-state objectives
3. action policy heads
4. long-horizon state transition heads
5. repo graph and symbol binding
6. edit localization
7. patch operator arguments
8. verifier-conditioned repair
9. bounded decoder CE
10. denoise repair
11. preference/listwise ranking
12. narrow RLVR
13. verifier-filtered SFT replay
14. stage-compiled distillation
```

The highest-value near-term design work is not choosing DPO versus RLVR. It is
ensuring that admitted data preserves the prerequisite structure needed for the
first eight stages: state, action, transition, graph, localization, operator,
and verifier-repair supervision.
