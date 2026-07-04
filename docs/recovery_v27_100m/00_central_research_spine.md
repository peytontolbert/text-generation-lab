# v2.7 100M Central Research Spine

This document reconstructs the central research spine for the 100M software maintainer after the workspace deletion incident.

## Final Objective

Finish v2.7 so the local 100M model beats Gemma-12B on the software-maintenance languages in scope:

- Python
- Rust
- C/C++
- JavaScript / HTML / TypeScript

The model must win in both settings:

- standalone weights
- full product harness

The evaluation must include expert-level maintainer behavior and anti-eval-hacking checks.

## Core Thesis

The 100M model should not be trained as raw free-form codegen first.

The correct spine is:

```text
structured software state
-> safe transition/action policy
-> repo graph grounding
-> bounded decoder
-> verifier-guided repair
-> product/harness integration
```

The decoder is one controlled action inside a software-maintenance loop, not the whole system.

The model should learn:

```text
repo/task/evidence state
-> classify surface
-> choose safe action
-> decide retrieve/correct/copy/build
-> maybe decode bounded output
-> verify
-> repair
```

Not:

```text
prompt -> free-form code
```

## Active Spine

The reconstructed durable spine is:

```text
intent-to-build strategy
-> repo_state_graph_v1
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder arguments
-> bounded decoder CE probe
-> measured decoder repair
-> scale judged curriculum
-> controlled maintainer loop
-> product/harness integration
```

This is the path that connects structured policy to actual software-maintenance competence.

## What Was Structurally Solved Before Deletion

The branch had structurally completed these layers:

- intent-to-build strategy
- repo_state_graph_v1 seed substrate
- symbol binding objective
- edit localization objective
- patch operator objective
- verifier repair objective
- bounded decoder argument surface
- bounded decoder CE candidate package
- tiny bounded decoder CE probe authorization

The project was not complete. It had reached the first tiny bounded decoder CE execution probe.

## What Was Not Yet Proven

Still unproven:

- the 100M learned the bounded decoder objective robustly
- decoder outputs are contentful and non-repetitive
- bounded decoder improves standalone behavior
- full product harness improves
- 100M beats Gemma-12B
- hidden-reference scoring is clean
- runtime/source/body emission is safe
- controller merge/promotion is ready

The step-10 probe loss was evidence that the tiny run started, not evidence of capability.

## Research Law

The project should optimize for this:

```text
train safe software transitions
then allow bounded decode
then repair decode through verifier feedback
then scale only judged rows
```

Do not revert to:

```text
mine raw code
-> train decoder
-> hope scale fixes it
```

## Resume Order

After repository recovery:

1. Restore code and artifacts from local/remote sources.
2. Patch cleanup safety before any training.
3. Recreate or recover stages through the last safe frontier.
4. Re-audit the bounded decoder CE tiny command.
5. Rerun tiny probe only after cleanup guard is proven safe.
6. Audit telemetry before any expansion.
7. Expand bounded decoder only if telemetry supports it.

