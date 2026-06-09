# MoE vs Dense Sweep Plan For Tiny Semantic Compression

Last updated: 2026-05-27

## Why This Belongs In The Research Program

Yes: dense-only sweeps are not enough. If the hypothesis is that tiny models need better compression algorithms, then sparse expert routing is directly relevant. A dense tiny model must store every behavior in one shared parameter space. A sparse or modular model can spend different parameter subsets on different semantic residuals, while keeping active compute small.

The question is not simply whether MoE has better perplexity. The question is:

```text
Does sparse expert specialization increase verified semantic bits per active parameter,
per total parameter, and per training token?
```

## Research Context

Switch Transformer showed that sparse expert routing can scale parameter count while keeping per-token compute lower, using simple top-1 routing. Its main lesson for this project is that active parameters and total stored parameters must be measured separately.

Sparse Upcycling showed that converting dense checkpoints into sparse MoE models can reuse dense training cost and outperform continued dense training in some settings. This matters because our current best deployable model is dense, but we may be able to add experts as residual capacity rather than restarting.

DeepSeekMoE focuses on expert specialization with shared and routed experts. That is relevant to tiny semantic compression because some knowledge is shared across all tasks, while residual facts, exceptions, and operations may benefit from routed specialists.

Mixtral demonstrates a practical sparse MoE language model where active compute is much smaller than total parameters. Its lesson for our metrics is that a model can have high total memory but lower active compute.

ModuleFormer is especially aligned with our question: modular/expert structure can support efficiency, specialization, extendability, and pruning. That maps directly onto recursive residual compression.

Relevant primary sources:

- Switch Transformer: https://arxiv.org/abs/2101.03961
- Sparse Upcycling: https://arxiv.org/abs/2212.05055
- DeepSeekMoE: https://arxiv.org/abs/2401.06066
- Mixtral of Experts: https://arxiv.org/abs/2401.04088
- ModuleFormer: https://arxiv.org/abs/2306.04640
- ST-MoE: https://arxiv.org/abs/2202.08906
- Expert Choice Routing: https://arxiv.org/abs/2202.09368

## Controls We Need

MoE can look better or worse depending on the denominator. Every experiment must report all of these:

| metric | why it matters |
|---|---|
| total parameters | memory/storage cost |
| active parameters/token | inference compute cost |
| router parameters | overhead that can dominate tiny models |
| verified bits / total parameter | storage efficiency |
| verified bits / active parameter | compute-path efficiency |
| verified bits / training token | data efficiency |
| router entropy | whether routing is confident or diffuse |
| load balance | whether experts are used or dead |
| expert specialization | whether experts separate by operation/domain/residual |
| residual replay gain | whether routed experts absorb failures better than dense |

## First Sweep Matrix

Use Stage430/431 because they include multiple semantic operation types:

- direct facts
- reverse lookup
- false-claim rejection
- default rules
- exceptions
- two-hop composition
- content-only answer decoding

Dense baselines already started:

| baseline | params | current signal |
|---|---:|---|
| dense 100k Stage430 | 135k | retrieval top1 0.9622, direct generation weak |
| dense 1M Stage430 | 645k | retrieval top1 0.9831, direct generation weak |

MoE candidates:

| candidate | active target | total target | routing | expert role |
|---|---:|---:|---|---|
| MoE-100k-active-4x | ~100k | ~250k-400k | top-1 | operation/domain experts |
| MoE-100k-active-8x | ~100k | ~500k-800k | top-1 | finer residual experts |
| MoE-1M-active-4x | ~1M | ~2M-4M | top-1/top-2 | larger semantic experts |
| shared-plus-routed | dense shared trunk + tiny experts | variable | shared + routed | shared grammar, routed residuals |
| upcycled dense-100k | start from dense 100k | +experts | initialized experts | residual specialization |

## Expert Placement

Start with MLP experts only. Attention experts are a later experiment.

Candidate placements:

1. Encoder MLP experts only: tests semantic compression geometry.
2. Decoder MLP experts only: tests answer emission.
3. Retrieval projection experts: cheapest sidecar experiment.
4. Shared encoder plus routed residual adapters: likely best tiny-model path.

For this project, the first implementation should avoid a full Switch-style distributed MoE. We only need tiny local experts:

```text
h -> router(h) -> top expert adapter -> residual update
```

This keeps overhead measurable and prevents routing complexity from hiding the result.

## Expected Outcomes

Possible result A: MoE wins on verified bits/active-param.

This would support the idea that tiny semantic compression benefits from modular residual storage.

Possible result B: dense wins at 100k, MoE wins at 1M+.

This would mean router overhead is too expensive at very small scale, but expert specialization helps once there is enough width.

Possible result C: MoE wins retrieval but not decoding.

This would match our current bottleneck: semantic access learns faster than free autoregressive answer emission. Then the next step should be pointer/copy decoding, not larger experts.

Possible result D: MoE loses everywhere.

Then dense plus residual replay is currently the better compression algorithm, and experts should be deferred until the curriculum is harder.

## First Decision Rule

Promote an MoE variant only if it improves at least one of these without harming the others badly:

```text
verified bits / active parameter
verified bits / training token
residual replay gain
Stage430 operation balance
direct answer recall
```

Do not promote a model just because total-parameter top1 improves. That would violate the tiny-model compression objective.

## Implementation Notes

The codebase now exposes an opt-in encoder/decoder MoE MLP path through `ModelConfig` and the training flags:

```text
--moe-num-experts
--moe-top-k
--moe-apply-encoder
--moe-apply-decoder
--moe-load-balance-weight
```

Dense remains the default with `--moe-num-experts 0`.

Recommended first patch:

```text
Dense encoder block
  -> shared MLP
  -> optional routed residual expert adapter
  -> residual add
```

Router logs required:

- expert counts
- router entropy
- mean selected expert by operation
- dead expert count
- top expert per source type

The first useful sweep is:

```text
dense 100k vs routed-adapter 100k-active
dense 1m vs routed-adapter 1m-active
Stage430 retrieval + direct generation + residual replay
```

This makes MoE part of the verified-bits research rather than a separate architecture experiment.

## First Measurement

Stage429 answer-card retrieval, 100-step, 100k-scale encoder-MoE experiments:

| run | params | routing | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---|---:|---:|---:|---:|
| dense 100k-100 baseline | 135,034 | dense | 0.8915 | 0.9412 | 0.00712504 | 46345.9 |
| encoder MoE 4x top-1 | 92,928 | hard top-1, detached combine weights | 0.1628 | 0.3030 | 0.00207679 | 12300.5 |
| encoder soft-MoE 4x | 92,928 | all experts active | 0.1452 | 0.2793 | 0.00185180 | 10968.0 |
| dense + routed residual adapter | 76,224 | dense MLP plus 4x adapter dim 8 | 0.8114 | 0.8951 | 0.01034931 | 74730.6 |

Interpretation: this tiny retrieval curriculum strongly rejects full MLP expert replacement, but the routed residual-adapter variant is useful. It has lower raw top1 than dense `100k-100`, but it is better on verified bits per training token and verified bits per parameter under the shorter-token setup.

The next MoE attempt should be residual replay on the routed residual-adapter model:

```text
train dense+routed-residual -> probe train failures -> residual replay -> measure held-out top1 and density
```

If residual replay raises the adapter model from `0.8114` toward the dense baseline while preserving the density advantage, experts become relevant for recursive semantic compression. If it does not, dense `100k-100` plus residual replay remains the better algorithm.

## Updated Measurements

Stage429 residual replay on the routed residual adapter was positive but did not beat dense replay:

| run | params | top1 | MRR | read |
|---|---:|---:|---:|---|
| dense + residual replay | 135,034 | 0.9674 | 0.9835 | best raw held-out answer-card retrieval |
| routed residual adapter + replay | 76,224 | 0.9091 | 0.9517 | beats dense raw `100k-100`, better density, but worse than dense replay |

Stage430 semantic ops exposed a data issue: the original `reverse_lookup` task was under-specified because many field/value pairs map to multiple entities. That created false negatives. The cleaned Stage432 variant uses set-valued reverse lookup targets.

| run | params | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|
| dense 100k Stage432 set-reverse | 77,664 | 0.9702 | 0.9843 | 0.00507007 | 74123.9 |
| routed residual adapter 100k Stage432 set-reverse | 80,000 | 0.9796 | 0.9882 | 0.00511929 | 72658.2 |
| routed residual adapter + residual replay | 80,000 | 0.9890 | 0.9945 | 0.01033703 replay-only | 73356.8 |
| routed residual adapter + fixed LB 0.1 | 80,000 | 0.9796 | 0.9882 | 0.00511929 | 72658.2 |
| routed residual adapter + fixed LB 0.1 + replay | 80,000 | 0.9874 | 0.9935 | 0.01032062 replay-only | 73240.4 |
| routed residual adapter + scheduled LB 0.1 | 80,000 | 0.9796 | 0.9885 | 0.00511929 | 72658.2 |
| routed residual adapter + scheduled LB 0.1 + replay | 80,000 | 0.9843 | 0.9919 | 0.01028781 replay-only | 73007.5 |

Interpretation: once the reverse-lookup target is semantically correct, the routed residual adapter gives a real raw-accuracy improvement on the multi-operation curriculum. Its verified bits/Mparam is slightly lower than dense because it has a few more parameters, but its top1 and bits/token are higher. This is the first clean evidence that small routed residual experts can help semantic operation balance rather than only compress answer-card lookup.

Residual replay from the routed-adapter checkpoint was also positive. Train-side probing found only 58 misses and 56 near misses, but replaying them still lifted held-out top1 from `0.9796` to `0.9890`. This is the best Stage432 held-out retrieval result so far.

The first load-balance run exposed and fixed a metric bug: the previous `moe_load_balance_loss` averaged across the expert axis when `dim=-1`, making the penalty effectively zero. After fixing the metric, `--moe-load-balance-weight 0.1` substantially balanced router usage without changing first-stage top1. Constant balance replay reached `0.9874`; scheduled warmup/cosine replay reached `0.9843`. Neither beats the lower-balance replay checkpoint, so balanced routing is healthier but not yet a raw-accuracy win.

The remaining Stage432 misses are no longer mainly label ambiguity:

| run | main misses |
|---|---|
| dense 100k Stage432 | reverse_lookup_set 10, rule_default 6, direct_fact 3 |
| routed residual adapter Stage432 | reverse_lookup_set 7, direct_fact 6 |
| routed residual adapter + replay | reverse_lookup_set 5, rule_default 1, direct_fact 1 |

Next MoE work should add operation-aware router diagnostics. If experts are actually specializing, selected expert distributions should differ across `direct_fact`, `reverse_lookup_set`, `rule_default`, `exception`, `false_claim`, and `two_hop_owner_region`.

## Stage433 Operation-Token Probe

Stage433 tested a simple operation-conditioned route: prefix every retrieval query and doc with explicit operation tokens such as `<AK_OP_DIRECT_FACT>` and `<AK_OP_REVERSE_LOOKUP_SET>`.

| run | params | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|
| Stage433 op-token routed residual | 81,984 | 0.9796 | 0.9887 | 0.00430726 | 70899.9 |
| Stage433 op-token routed residual + replay | 81,984 | 0.9874 | 0.9928 | 0.00868355 | 71468.0 |
| Stage434 special-op-token routed residual | 82,432 | 0.9922 | 0.9958 | 0.00523043 | 71418.6 |
| Stage434 special-op-token routed residual + replay | 82,432 | 0.9937 | 0.9969 | 0.0104774 | 71531.6 |
| Stage435 hard router-op CE w=0.02 | 82,432 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| Stage436 balanced router-op CE w=0.02 | 82,432 | 0.9906 | 0.9950 | 0.00522215 | 71305.6 |
| Stage437 balanced router-op CE w=0.005 | 82,432 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| Stage438 router-operation MI w=0.01 | 82,432 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| Stage439 second residual replay | 82,432 | 0.9953 | 0.9976 | 0.013992 | 71644.6 |
| Stage440 third residual replay | 82,432 | 0.9953 | 0.9976 | 0.0209879 | 71644.6 |

Stage433 was not better than Stage432. The first-stage top1 ties the Stage432 routed residual run, but the op-token prefix raises average retrieval-pair length from about `88.7` to `105.4` tokens, so verified bits/token drops. Replay also tops out at `0.9874`, below the Stage432 low-balance replay checkpoint at `0.9890`.

Stage434 fixes the token economics by adding the operation markers to the AgentKernel special-token library. That changes the result: average retrieval-pair length falls to about `87.9` tokens, first-stage top1 reaches `0.9922`, and residual replay reaches `0.9937`. This is the best cleaned semantic-ops checkpoint so far.

Stage435-437 test direct router-operation supervision. The naive token-weighted CE collapses toward high-volume operations. Balancing the router CE by operation fixes the interpretability problem, but both `0.02` and `0.005` still reduce top1 to `0.9906`. Stage438 replaces fixed labels with a mutual-information objective between operation IDs and router probabilities; it improves operation-specific routing structure but lands on the same `0.9906` top1. Router shaping is therefore still too blunt for the current tiny encoder; compact operation tokens are enough signal.

Stage439 applies a second residual replay pass from the Stage434 replay checkpoint, using 26 train misses plus 26 near misses mixed with the original train set. This improves held-out top1 from `0.9937` to `0.9953`. Stage440 applies a third smaller residual pass from 15 train misses and 15 near misses, but held-out top1 plateaus at `0.9953`. The useful conclusion is that recursive residual replay still works after the first pass, but the remaining failures are not generic; they are specifically set-valued inverse lookup confusions.

Stage441-442 test that diagnosis directly by adding `lookup_key=domain|field|answer` to only reverse lookup rows. The key adds token overhead, raising average retrieval-pair length to about `96.1`, but it improves the hard slice. Stage441 from scratch reaches `0.9937` top1 and Stage442 with one residual pass reaches `0.9969` top1 / `0.9982` MRR, the best semantic-ops result so far. Stage443-444 broaden the key idea to every operation with `semantic_key=...`; direct facts become perfect, but the average pair length rises to about `123.4` tokens and held-out top1 stays at `0.9953`. Narrow structural keys beat broad keys.

Stage445-447 expand the curriculum from retrieval to set use with `set_count` and `set_member` operations over the reverse lookup sets. Stage445 reaches `0.9974` top1 / `0.9987` MRR over 1,163 held-out pairs with an 84,992-parameter model. Direct facts, reverse sets, rules, exceptions, false claims, and two-hop composition are perfect; the remaining errors are in the new set-count and set-member rows. Stage446 residual replay plateaus at the same score, proving that more exposure is not the fix. Stage447 then removes the full entity list from count/member answer cards and reaches `1.0000` top1 / `1.0000` MRR while cutting average retrieval-pair length from about `101.9` to `97.8` tokens. This is a target-compression win, not a router win.

Stage448-452 add two-constraint derived set operations: `set_intersection_count` and `set_intersection_member`. Stage448 reaches `0.9986` top1 / `0.9993` MRR over 1,474 held-out pairs with an 87,488-parameter model, and both new intersection slices are perfect. The residual errors are direct same-entity wrong-field confusions. Stage449 adds a narrow direct-fact key, which improves direct facts slightly but hurts `rule_default`; Stage450 residual replay from Stage448 also does not improve total top1. Stage451 compacts direct fact cards to only the queried field and answer; it lowers eval loss but does not improve held-out top1 and introduces a reverse-set miss. Stage452 preserves the full direct card but prefixes `selected_field` and `selected_answer`; it ties Stage448 on verified retrieval with lower eval loss, so it is useful diagnostically but not a verified-access improvement. The current best derived-set checkpoint is Stage448, and the next likely fix is direct-card factorization or a value-selector head, not broader key prefixes or shorter direct cards alone.

Stage453-459 test that factorization path. Stage453 changes direct facts into compact value cards and adds separate `entity_context` cards with full entity fields; direct facts and entity context become perfect, but default-rule rows regress. Stage456 is the best 87k-scale design: factorized direct cards plus narrow `rule_key=op|domain|entity|field` prefixes for rule/default and exception rows. It reaches `0.9993` top1 / `0.9997` MRR over 1,512 held-out pairs, with every operation perfect except one direct-field collision. Stage457 adds direct fact keys too, but that shifts errors into false-claim and reverse lookup. Stage458 mild residual replay from Stage456 also does not clear the final direct miss. Stage459 scales the Stage456 target design to the `1m` preset, 515,872 actual parameters here, and reaches `1.0000` top1 / `1.0000` MRR across all 11 operations. That is a useful scale-map signal: the last 87k miss is likely representation-resolution limited under this architecture.

Router diagnostics show healthier spread than the original collapsed Stage432 router, but still no clean operation experts:

| checkpoint | side | total expert probabilities | entropy | top expert pattern |
|---|---|---|---:|---|
| Stage433 first-stage | query | `[0.2117, 0.2156, 0.3573, 0.2154]` | 1.959 bits | expert 2 for every operation |
| Stage433 first-stage | doc | `[0.1804, 0.2069, 0.3830, 0.2298]` | 1.934 bits | expert 2 for every operation |
| Stage433 replay | query | `[0.2091, 0.2174, 0.3585, 0.2150]` | 1.958 bits | expert 2 for every operation |
| Stage433 replay | doc | `[0.1848, 0.2047, 0.3819, 0.2286]` | 1.936 bits | expert 2 for every operation |
| Stage434 first-stage | query | `[0.1761, 0.2250, 0.1722, 0.4267]` | 1.887 bits | mostly expert 3 |
| Stage434 first-stage | doc | `[0.2853, 0.2144, 0.1160, 0.3843]` | 1.883 bits | expert 3 except exceptions |
| Stage434 replay | query | `[0.2455, 0.2251, 0.1428, 0.3867]` | 1.913 bits | split between experts 0 and 3 |
| Stage434 replay | doc | `[0.3530, 0.2151, 0.1081, 0.3238]` | 1.881 bits | split between experts 0 and 3 |
| Stage436 balanced CE | query | `[0.2873, 0.1948, 0.2326, 0.2854]` | 1.982 bits | clean operation split |
| Stage436 balanced CE | doc | `[0.2612, 0.1154, 0.3545, 0.2689]` | 1.905 bits | cleaner but accuracy lower |

Interpretation: operation tokens are useful app-side structure only when they are compact. Literal text prefixes add overhead and do not make the residual adapter specialize semantically. Atomic operation tokens improve both accuracy and token efficiency, targeted reverse lookup keys improve inverse-set ambiguity, compact set-operation cards solve the first derived set-use slice, and Stage448 shows two-constraint set intersections are learnable with the same small routed residual architecture. Explicit router supervision and MI regularization improve interpretability but hurt retrieval. The next operation-aware MoE attempt should improve target/schema representations before forcing cleaner expert assignments.

## Router Diagnostic

The first operation-aware router analysis was run on the Stage432 routed-residual replay checkpoint:

```text
runs/local/artifacts/knowledge_compression_moe_residual_100k_stage432_semantic_ops_set_reverse_steps200_residual_replay/router_by_operation_eval_stage432.json
```

Result: routing is not yet cleanly operation-specialized. Expert 1 dominates most query and document tokens:

| side | total expert probabilities | entropy |
|---|---|---:|
| query | `[0.0886, 0.5006, 0.2652, 0.1457]` | 1.722 bits |
| doc | `[0.1226, 0.5422, 0.1829, 0.1522]` | 1.712 bits |

After fixing load balance and training with `0.1` weight:

| side | total expert probabilities | entropy |
|---|---|---:|
| query | `[0.1350, 0.1603, 0.3366, 0.3681]` | 1.873 bits |
| doc | `[0.2195, 0.1792, 0.2867, 0.3146]` | 1.966 bits |

Before the fix, every operation had expert 1 as its top expert. With fixed load balancing, the router spreads load much more evenly and some operations prefer expert 2 or 3, but the split is still token-distributional rather than cleanly semantic. The Stage432 gain is still best explained as useful residual capacity plus partial token-level routing, not a mature operation-expert decomposition.

Next MoE architecture target:

```text
keep dense shared trunk
+ routed residual adapters
+ stronger load balance / entropy shaping
+ router diagnostics by operation and domain
+ compact operation-conditioned router input
```

Do not scale expert count yet. First make the router use the existing four experts more deliberately.

Current decision: keep the fixed load-balance metric and the schedule flag, but do not use high load-balance, long textual operation prefixes, hard router-operation CE, or router-operation MI as defaults. The best narrow semantic-ops checkpoint is Stage442. The best single-set expanded checkpoint is Stage447. The best 87k harder derived-set checkpoint is Stage456. The best overall derived-set checkpoint is Stage459, which reaches perfect held-out retrieval at 515,872 parameters.
