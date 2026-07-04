# 100M Software Maintainer Model Stack

The final system should be a multi-model / multi-head software maintenance stack, not a single free-form LLM.

## Stack Overview

```text
raw repo / user intent / logs / tests
-> structure extraction
-> memory + retrieval
-> planning
-> edit/operator prediction
-> bounded code/text generation or repair
-> verification
-> failure diagnosis
-> learning loop
```

## Roles By Model Family

| Component | Role |
| --- | --- |
| SSM / Mamba | Repo-wide compression, long logs, commit history, CI traces |
| GNN | Repo structure, call graphs, import graphs, dependency graphs, test graphs |
| Encoder / retriever | Evidence ranking, source grounding, file/symbol retrieval |
| Cross-encoder reranker | Query-file, failure-log-code, test-source ranking |
| Encoder-decoder | State transitions, bounded output, repair transforms |
| Decoder | Bounded candidates only |
| Denoiser / diffusion | Repair malformed, short, leaky, repetitive, or failed outputs |
| Linear / tree / MLP heads | Gates, rankers, confidence, OOD, route decisions |
| Reward / energy model | Patch quality, minimality, verifier-backed preference |
| Symbolic tools | AST, type checker, compiler, linter, tests, static analyzer |
| Verifiers | Authority, exact checks, safety gates, acceptance |

## Core Architecture

```text
User intent
-> intent classifier / encoder
-> repo-wide scanner + indexes
-> retrieval + reranking
-> graph builder / GNN
-> compressed repo state packet
-> transformer planner
-> structured policy heads
-> edit operator predictor
-> bounded decoder or denoising editor
-> verifier stack
-> repair loop
-> memory update
-> dataset judge / curriculum compiler
```

## Current 100M Student Role

The 100M seq2seq model should focus on:

- semantic state transitions
- structured heads
- bounded decoder arguments
- small patch/plan rendering
- repair transforms after verifier feedback

It should not be forced to:

- infer repo-wide structure alone
- memorize all repos
- produce full files from scratch
- bypass deterministic budget and authority gates

## Fusion Principle

Use each signal where it is strongest:

```text
structured head logits
+ deterministic budget overlay
+ junk ranker route
+ retrieval/evidence confidence
+ verifier result
= effective action / decode decision
```

The learned model may propose. Contracts authorize.

## Gate Fusion

Effective decode should be:

```text
effective_decode_allowed =
  learned_decode_allowed
  AND deterministic_budget_ok
  AND action_allows_decode
  AND evidence_allows_decode
  AND junk_ranker_route in {KEEP_BOUNDED_DECODER, USE_FOR_DENOISE_REPAIR}
  AND structured_head_confidence_ok
```

Budget safety is deterministic, not model authority.

## Denoising Role

Denoising/diffusion is not the primary first-pass coder.

It owns repair:

```text
bad output / failed patch / verifier failure
-> clean bounded output / repaired patch / corrected state
```

Use it for:

- internal-token cleanup
- short-output expansion
- repetition repair
- wrong-surface repair
- syntax repair
- failed-test patch revision
- verifier-log normalization

