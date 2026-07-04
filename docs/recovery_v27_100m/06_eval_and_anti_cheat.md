# Expert Maintainer Eval And Anti-Eval-Hacking

The final objective requires more than benchmark score.

The 100M must beat Gemma-12B in standalone and full product harness without shortcutting the eval.

## Evaluation Targets

Languages:

```text
Python
Rust
C/C++
JavaScript / HTML / TypeScript
```

Modes:

```text
standalone weights
full product harness
```

Skill areas:

```text
intent -> build strategy
repo graph -> relevant files/symbols
symbol use -> definition/import/test relation
failure log -> root cause class
root cause -> edit operator
edit operator -> bounded patch args
patch -> verifier expectation
verifier failure -> repair/abstain
```

Do not evaluate only final text similarity.

## Expert Maintainer Rubric

An expert-level maintainer eval should check:

```text
understands user intent
uses allowed imports only
rejects blocked imports
retrieves source evidence when needed
binds symbols correctly
localizes edit scope
chooses minimal edit operator
creates/updates tests when appropriate
predicts verifier command
interprets verifier failure
repairs or abstains safely
keeps patch minimal
avoids broad rewrites
avoids hallucinated symbols
avoids internal tokens
produces contentful final answer
```

## Anti-Eval-Hacking Checks

Every eval should check:

```text
no hidden-reference materialization
no target text in input
no label-coded IDs
no surface marker shortcut
no requested-output-type shortcut
no duplicate semantic key leakage
no split overlap
no raw source/body leakage unless intended
no long target truncation
no metadata-only baseline dominance
no graph-degree-only baseline dominance
no verifier result leakage
no Gemma teacher text treated as ground truth
```

## Baselines To Track

For each structured objective:

```text
majority baseline
single-feature baseline
combo-feature baseline
metadata-only baseline
field/prior-only baseline
surface-marker baseline
requested-output-type baseline
graph-degree baseline
query-node baseline
```

Training should be blocked if shortcut baselines dominate.

## Decoder Quality Gates

Decoder/generation evals need:

```text
internal_token_leak_rows == 0
short_or_junk_rate == 0
degenerate_repetition_rate near 0
contentful_output_rate high
target_prefix_match tracked
EOS/length behavior tracked
row-token loss tracked
high-confidence wrong rows tracked
```

Zero leak alone is insufficient because suppression can collapse generation to empty output.

## Product Harness

Full product harness scoring must remain separate from training data generation.

Never use:

```text
hidden reference
hidden scorer output
Gemma output
runtime result
body/source emission
```

as target truth unless explicitly authorized and quarantined.

## Standalone vs Harnessed

Earlier same-harness evidence showed standalone 100M was the weak link.

The evaluation must preserve:

```text
standalone engine score
harnessed product score
Gemma score
same prompt/task surfaces
same scoring constraints
```

The objective is not satisfied unless standalone weights and full product harness both beat Gemma-12B.

