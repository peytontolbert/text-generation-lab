# Curriculum Compiler And Dataset Judge

The project moved from isolated dataset fixes toward a closed-loop curriculum compiler.

## Closed Loop

The intended loop is:

```text
dataset
-> dataset judge / junk ranker
-> curriculum compiler
-> probe/train
-> audit
-> failure attribution
-> repair manifest
-> dataset/ranker update
-> next probe
```

## Row Routing

Every row must have an objective-aware route.

Known routes:

```text
KEEP_STRUCTURED
KEEP_BOUNDED_DECODER
HOLD_LONG_OUTPUT
USE_FOR_DENOISE_REPAIR
USE_AS_NEGATIVE
NEEDS_RETRIEVAL
QUARANTINE_LABEL_CONFLICT
DROP_DUPLICATE
```

A row can be good for one objective and bad for another.

Example:

```text
long HTML row:
  bad for decoder CE
  good for long-output holdout
  good for budget classifier
```

## Hard Dataset Law

Every active row should declare:

```text
canonical schema
semantic label / action label
evidence state
surface family
operation cell
authority lane
counterfactual sibling where applicable
loss mask
row route
no leakage status
no shortcut dominance status
split/surface/cell coverage
```

## Loss Mask Law

Every manifest row should declare exactly which losses are allowed.

Example:

```json
{
  "row_id": "...",
  "route": "KEEP_STRUCTURED",
  "losses_enabled": {
    "surface_role_ce": true,
    "repair_surface_ce": true,
    "action_ce": true,
    "decoder_ce": false,
    "denoise_ce": false,
    "runtime_reward": false
  },
  "reason": "structured transition row; decoder not authorized"
}
```

This connects:

```text
dataset judge -> PyTorch loss function -> gradients
```

## Important Judge Signals

The deterministic dataset junk/routing ranker should detect:

```text
target_over_budget
long_blob
html_doc_fragment
decoder_target_truncated
raw_internal_token_in_decoder
raw_text_leak_in_structured_objective
short_or_junk_target
degenerate_repetition_target
missing_evidence_but_decode_allowed
budget_bad_but_decode_allowed
action_label_ambiguous
surface_role_conflict
duplicate_semantic_key
split_overlap
shortcut_dominated_feature
teacher/verifier disagreement
```

## Shortcut Audit Rule

Do not train if:

```text
single-feature baseline solves the task
combo-feature baseline solves the task
metadata-only baseline dominates evidence-aware model
surface/request marker shortcut dominates
graph-degree-only baseline dominates
```

For task objectives, require:

```text
strongest shortcut baseline < gate ceiling
evidence-aware model beats shortcut baseline
heldout exactness by cell is reported
collapse rate is reported
```

## Canonical Graph Rule

For active curriculum rows, require counterfactual/mixed obligations:

```text
positive original
evidence removed
contradictory / unsafe twin
mixed replay obligation
```

This prevents local positive-only islands.

## Static vs Learned Proof

Important distinction:

```text
compiler can assign correct label
!=
model learned transition function
```

Training readiness requires:

```text
beats metadata shortcut baselines
counterfactual flip accuracy
evidence removed -> retrieve
no high-confidence wrong accepts
per-surface exact
per-obligation exact
no collapse
no leakage
```

## Cell-Level Import Policy

Correct examples are not automatically good training rows.

Imports can distort shared boundaries.

Candidate cells should be assigned:

```text
KEEP
PRUNE
LOWER_WEIGHT
FINE_ABLATION_ONLY
REQUEST_COUNTERBALANCE
```

based on shared-row impact, not just row correctness.

## Scale Plan

Do not scale raw Python files.

Scale by transition type:

```text
150k intent/build strategy
150k repo graph / symbol binding
150k edit localization
150k patch operator
150k verifier/failure diagnosis
150k repair/denoise episodes
100k abstain/retrieve/missing evidence
100k bounded rendering
```

Every scaled row must pass judge/ranker and objective-specific routing.

