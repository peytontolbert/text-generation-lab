# Full Research Timeline

Last updated: 2026-06-06

This is the consolidated timeline for the AgentKernel/PocketPal tiny-model semantic-compression research in this repository. It is compiled from the docs in `docs/` and the local artifact index in `docs/active_knowledge_compression_research.md`. The purpose is to preserve the whole arc: what was tried, what became accepted evidence, what was rejected, and what claims are still out of bounds.

## Claim Boundary

Current accepted frontier:

- Tiny-model KBPP research supports verified semantic access and controlled candidate ranking, not broad free-form intelligence.
- The current controlled same-candidate 100M frontier is Stage1069: `350/640` answer and `333/640` exact on both eval and salted hidden transfer. It reaches the Stage1040 typed-interface recoverable ceiling without bridge fields, char-comparator access, deterministic suffix set intersection, or explicit pair-anchor candidate-scoring inputs.
- Stage1070 preserves the Stage1069 frontier through constrained answer materialization with `640/640` parse reliability.
- Stage1083 shows a possible next ceiling, projecting Stage1069 plus learned composition proof-pool expansion to `379/640` answer and `362/640` exact, but the proof-pool construction is still external and is not an accepted bridge-free final claim.

Current non-claims:

- No direct/free-form generation parity claim. Stage1078 rejects ordinary decoder CE: encoder-frozen direct decoder tuning scores `0/100` top-1 and full-model tuning scores `1/100` on structured direct-value ranking.
- No broad 7B/12B general-knowledge parity claim. The 100M wins are same-candidate controlled-ranking results.
- No pure neural proof for every earlier high score. Some milestones are deterministic verifier/filter ceilings or typed-interface ceilings and are labeled as such.

## Timeline Summary

| stage range | focus | result | status |
|---|---|---|---|
| Stage429-432 | Initial answer-card and semantic operation ladders | 100k residual replay reaches `0.9674` top1; Stage432 cleans reverse lookup and reaches `0.9890` with replay. | Establishes KBPP/token and residual replay loop. |
| Stage433-447 | Operation tokens, binding keys, compact set operations | Special operation tokens and narrow reverse keys help; Stage447 reaches perfect retrieval on eight operations. | Accepted target-design lesson. |
| Stage448-470 | Derived intersections, factorized direct facts, rule sets, compact reverse | Stage470 reaches answer-perfect access at 523k; exact misses are mostly answer-equivalent proof swaps. | Accepted expanded semantic curriculum. |
| Stage471-575 | Scale ladder and tiny-density frontier | 16k is raw bits/parameter leader; 26k is high-reliability answer-perfect frontier; key-anchor attempts damage membership proof geometry. | Accepted density map; reject key-anchor continuations. |
| Stage591-615 | Collision-conditioned KBPP and selector schemas | Stage596 introduces non-unique keys; Stage599 improves collision recovery; Stage615 minimal raw `entity|field` selector is best entity-context route. | Accepted schema/selector evidence. |
| Stage616-660 | Recursive selector search and generalized KBPP surfaces | Colon selector wins; transfer to direct/two-hop/set/rule families; generalized 8 KBPP surface built, Stage660 remains insufficient. | Accepted selector-search method; generalized route still developing. |
| Stage661-759 | Atomic 256 and generalized KBPP factorization | Stage722 solves 256 via factorized key interaction; Stage733/735 pass generalized qidless/held-out alias 8 KBPP; Stage739/741 reach 16 and answer-32 KBPP; Stage758 defines 100M route. | Accepted factorization algorithm with leakage gates. |
| Stage774-840 | Direct-answer and hardened binding setup | Direct-answer decoder probes fail; candidate-ranking/value-feature routes improve; Stage819 hardens surfaces; Stage839/840 typed bridge channel route emerges. | Reject decoder path; shift to candidate ranking and hardened aliases. |
| Stage841-895 | Hardened held-out alias partitions and typed bridge access | Stage853 side-invariant typed partitioner reaches `237/220`; Stage884/887/895 recover typed-access frontiers up to `285/268`. | Accepted recoverable typed-access, not bridge-free. |
| Stage896-943 | Bridge-salt audit and model-side residual value heads | Salt audit supports fixed similarity; frozen hidden/encoder readouts mostly fail; Stage938/942 loadable value-module frontier reaches `252/235`. | Accepted model-side candidate-ranking frontier with caveats. |
| Stage944-981 | Loadable 100M bridge and pair-interface system | Stage976 bridge-free-ish model-owned frontier is `282/265`; Stage981 typed pair-interface reaches `342/325`. | Stage981 accepted as budgeted interface only. |
| Stage982-1041 | Comparator internalization and no-anchor typed interface | Learned/text/naturalized/no-anchor comparators progress; Stage1040/1041 reaches typed-interface ceiling `350/333`. | Accepted typed-interface result, not bridge-free equality. |
| Stage1042-1069 | Bridge-free learned pair/composer route | Frozen/encoder value heads fail; contrastive span-pair classifier plus candidate composer reaches Stage1069 `350/333` on eval and hidden. | Current accepted bridge-free controlled-ranking ceiling. |
| Stage1070-1083 | Materialization, direct generation, proof expansion | Constrained extraction works; direct decoder CE fails; learned composition proof expansion projects `379/362` with external proof pool. | Materialization accepted; direct generation rejected; proof expansion is next route. |

## Detailed Milestones

### Stage429-432: KBPP Measurement And Residual Replay

The first ladder treats answer-card retrieval as the semantic primitive and measures verified bits per token and per parameter. The useful scale band is not the largest model: 100k learns fast, 1M saturates reliability, and 10M loses parameter efficiency on this narrow task. The key result is the recursive loop: train, probe residual failures, replay residuals, and probe again.

Stage432 fixes reverse lookup by making ambiguous reverse answers set-valued. Dense 100k reaches `0.9702` top1, routed residual 100k reaches `0.9796`, and replay reaches `0.9890`. This establishes that curriculum correctness and residual replay can buy more than raw scale.

### Stage433-447: Operation Tokens, Binding Keys, And Compact Sets

Special operation tokens beat ordinary text markers because they reduce token overhead and make operation identity atomic. Router-shaping losses and mutual-information routing clean up routing but hurt retrieval, so the default remains compact operation tokens without heavy router pressure.

Narrow binding keys help only where ambiguity demands them. Reverse lookup keys help inverse-set ambiguity; broad semantic keys spend tokens on solved operations. Compact set count/member cards remove distracting full entity lists and Stage447 reaches perfect retrieval across direct facts, inverse sets, set count/member, rules, exceptions, false claims, and two-hop composition.

### Stage448-470: Derived Set Composition And Compact Proof Payloads

Stage448 adds set intersections and shows the model can bind two field constraints. Stages453-459 factor direct facts into value cards plus entity context, then add narrow rule keys; the 1M preset reaches perfect access, while 87k remains one direct-field miss short.

Stage460 adds rule case sets, and Stage461-464 add rule-case intersections. The important target-design result is that answer-equivalent exact misses can be proof-card swaps, especially `member=false` cards. Stage469-470 compact reverse lookup payloads while preserving keys and counts. Stage470 reaches answer-perfect retrieval across 2,088 held-out examples at 522,784 parameters.

### Stage471-575: Scale Ladder And Tiny-Density Frontier

The compact reverse/direct/false-claim/rule-card ladder maps a sharper breakpoint. The nominal 10k preset is 16,280 actual parameters and becomes the raw density frontier, but the 25,852-parameter `d_model=12` rung is the smallest high-reliability answer-perfect checkpoint.

Stage548 becomes the promoted verified-retrieval checkpoint under deterministic structured-key filtering. Stage563-566 make the verifier and promotion boundary enforceable. Stage575 and the Stage572/575 overlap audit reject auxiliary key-anchor pressure: it collapses membership proof neighborhoods, producing a shared failure attractor with Jaccard `0.9389` across misses.

Decision from this phase: deterministic structured-key filtering is a valid runtime contract, but not a pure neural KBPP claim. Further gains need harder collision surfaces and better target schemas, not key-anchor pressure.

### Stage591-615: Collision-Conditioned KBPP And Minimal Selectors

Stage595 proves the deterministic structured-filter ceiling on the current schema. Stage596 then makes the task harder by coarsening exact keys so filtering narrows candidates but does not solve every row. Stages597-599 train on this collision-conditioned surface and improve no-filter answer from `0.9104` to `0.9301`.

Entity-context remains weak until the schema changes. Stage601 replaces whole-entity context cards with field-level cards; Stage602 balances replay to keep direct/set slices from regressing. Stage606 maps the residuals as field-role binding errors. Stage607 role tokens help answer reliability but not pure-neural frontier. Stage610-615 show the stronger route: expose the latent selector pair cheaply. The best in this branch is Stage615, adding only raw `entity|field`, improving exact/answer to `0.9111` / `0.9286` while lowering token cost versus role-token scaffolding.

Decision: the tiny model benefits from making the right selector dimension cheap and explicit. Loss pressure alone exchanges errors.

### Stage616-660: Recursive Selector Search And Generalized Surfaces

Stage616 automates delimiter search and finds `entity:field` beats `entity|field`. Stages617-621 transfer the selector to direct facts and two-hop families. Stages622-627 search rule, field, reverse, and residual selectors. Stage628-633 canonicalize selector surfaces and test internalization. Stage634-638 move to rank-2/rank-3 residual bridges and confirm fresh entity rank-3 structure matters. Stage639-643 map direct/entity schema probes.

Stage644 creates the KBPP doubling harness. Stage645-651 expand to 72-domain collision-conditioned selector surfaces and rank-3 residual replay. Stage652 defines the generalized 256 KBPP route. Stage653-660 build and probe generalized 8 KBPP surfaces; early direct transfer is not enough, so the route shifts to factorized bridge/collision gates.

### Stage661-759: Factorized Binding And Generalized KBPP Gates

Stages661-688 map the atomic 256-rung boundary. Repeated residual replay and simple head capacity changes do not solve the residual collisions. Stage706 removes qid text and proves the old rung leaned on row identity. Stage711 is the best pure single-vector neural rung at `208/256` answer.

Stage722 is the corrected factorization result: late key-factor interaction reaches `256/256` exact/answer on the 256 rung. Stage723 shows the objective can train through that factor. Stage726 introduces accepted generalized collision gates so singleton selectors cannot solve the task. Stages732-735 pass the generalized 8 KBPP collision gate using natural domain/field/entity factors, qid removal, and held-out entity aliases. Stages737-741 scale to accepted 16 KBPP and answer-32 KBPP gates.

Stage758 packages the 100M factorized binding route and insists on qidless, held-out alias, no-answer-leakage gates before real 100M claims.

### Stage774-840: Direct Answer Failure And Hardened Binding Setup

The direct-answer branch starts early and repeatedly fails under ordinary decoder/value objectives. Candidate value ranking, route features, and operation conditioning produce more usable progress than free decoder CE. The research shifts from “make the decoder emit” to “make a verified candidate-ranking decision, then constrain materialization.”

Stage819 hardens the binding surface with alias/counterfactual constraints. Stage826-830 test held-out alias and external alias-salt validation. Stages831-840 explore external alias scorer weighting, operation-specific scorers, low-rank adapters, and typed bridge channels. These build the substrate for the later 100M hardened bridge work.

### Stage841-895: Hardened Held-Out Alias Partitions And Typed Bridge Access

Stage849 gives the metadata teacher partition ceiling: `479/640` answer and `465/640` exact. Token-only partition prediction initially fails, but Stage852/853 side-invariant typed bridge normalization becomes the accepted hardened internalization frontier at `237/640` answer and `220/640` exact, implied full `467/449`.

Frozen partition rerankers then add operation-specific gains. Stage866 accepts a margin-gated embedding reranker at `242/225`. Stage877 reaches `245/228`, Stage882 reaches `249/232`, and Stage883 relation typed bridge reranking lifts relation from `49/128` to `82/128`. Stage884 reaches `282/265`, and Stage895 reaches `285/268` with frozen normalized bridge embeddings. These are recoverable typed-access frontiers, not bridge-token-free model-owned claims.

### Stage896-943: Bridge-Salt Audit And Model-Side Residual Value Modules

Stage896-897 salted bridge suffixes preserve most relation gains, arguing against simple original-hash memorization, but the scorer still receives typed bridge tokens. Stage899-915 reject frozen hidden-state and localized span readouts: existing frozen 100M representations do not expose bridge equality well enough.

Stage916-919 patch composition qslot/proof geometry and recover typed-access capacity. Stage920-925 reject frozen-hidden and cached encoder CE routes. Stage926 accepts a frozen embedding residual value head at `240/223`; Stage928 operation-gates it to `248/231`; Stage929 adds a relation specialist; Stage933 makes the combined `251/234` policy reproducible. Stage938 loads accepted specialist heads into one module, and Stage942/943 advance the policy to `252/235`, implied full `482/464`.

Decision: small value modules can improve controlled candidate ranking, but direct internalized bridge equality remains unresolved.

### Stage944-981: Loadable 100M Pair Interface

Stage944 makes the Stage943 policy loadable. Stage946-959 audit the model-side gap and relation qslot/value auxiliaries. Stage961-968 develop full-pair equality/count and pair arity routing. Stage976 is the loadable 100M pair-teacher model-owned frontier at `282/265`.

Stage981 combines Stage976 with a declared counted pair-overlap/count interface and a 97-parameter router for composition/relation. It reaches `342/640` answer and `325/640` exact on eval, with implied full `572/554`. Stage991 extends the claim gate against local Qwen3 8B, Qwen3.5 9B, and Gemma3 12B prompt baselines and passes. The claim is explicitly budgeted-interface evidence, not bridge-free model-owned equality.

### Stage982-1041: Learned Comparators And No-Anchor Typed Interface

Stage997 replaces deterministic suffix set intersection with a learned encoder-span equality/count comparator, reaching `336/319`, but still uses qpair/dpair marker locations. Stages1003-1007 remove structured bridge fields and self-locate rendered markers from text, preserving the Stage981 frontier. Stages1008-1012 naturalize side-specific markers into side-neutral anchors and preserve `342/325`.

Stages1013-1025 remove explicit anchors and move to schema entity/slot equality. Stage1025 reaches `334/317` with no-anchor learned character schema equality. Stages1030-1041 add learned char-schema policy, role awareness, source/default-kind operators, and exception/counterfactual fixes. Stage1040/1041 reaches the typed-interface recoverable ceiling: `350/640` answer and `333/640` exact, implied full `580/562`, beating Stage981 by `8/8` and beating same-candidate 8B/9B/12B prompt baselines.

Decision: this is the best typed-interface result, but it still uses a declared learned string comparator and typed operators. It is not bridge-free encoder-owned equality.

### Stage1042-1069: Bridge-Free Learned Pair/Composer Route

Stage1042 defines the bridge-free internalization contract: no external char comparator, no bridge fields, no deterministic suffix set intersection, and no explicit pair anchors. Stages1043-1044 export operator-teacher targets and a salted hidden no-anchor split.

Stages1045-1047 reject frozen and simple encoder-trainable scalar value heads. Stage1048 shifts to pair/span operator heads. Stage1049 rejects simple span-operator scoring. Stage1051 exports `43,951` contrastive span-pair examples; Stage1052 trains a frozen-100M pair classifier with high calibration and hidden-transfer accuracy. Stage1054 reaches `311/294`; Stage1055 gates it as the first accepted bridge-free learned-pair frontier, beating Stage976 and Gemma3 12B but still below Qwen3 8B.

Stage1056 trains a learned candidate composer over pair probabilities, base score, rank, and operation id, reaching `329/312`; Stage1057 gates it as beating Qwen3 8B, Qwen3.5 9B, and Gemma3 12B. Stage1060 audits composition misses and finds missing target-entity supervision. Stage1061-1065 add target-entity span-pair supervision and reach `338/321` eval plus `350/333` salted hidden. Stage1068 changes alpha tie-breaking and Stage1069 gates the current ceiling: `350/333` on both eval and salted hidden transfer, matching the Stage1040 typed-interface recoverable ceiling.

Decision: Stage1069 is the current accepted bridge-free controlled same-candidate ranking result. It beats Stage976 by `68/68`, Qwen3 8B by `33/33`, Qwen3.5 9B by `29/29`, and Gemma3 12B by `41/41`. It remains candidate ranking, not direct/free-form generation parity.

### Stage1070-1083: Materialization, Direct Generation, And Proof Expansion

Stage1070 extracts typed `answer=<value>` from Stage1069 selections and preserves `350/333` with `640/640` parse reliability. Stage1071 exports direct-answer distillation rows. Stage1072-1078 test whether ordinary decoder CE can make the 100M model directly rank/generate answer values. It cannot: Stage1074 encoder-frozen decoder tuning scores `0/100` top-1 and Stage1076 full-model tuning scores `1/100` top-1 on structured direct-value ranking. Stage1078 rejects direct-generation completion.

Stage1079-1080 explore answer/value-head and candidate-support ceilings. Stage1081-1083 move toward proof-pool expansion. Stage1083 uses the learned Stage1062 span-pair classifier to score split-local composition proof-pool expansion. Composition improves from `58/42` to `87/71`, and the projected Stage1069-plus-proof-pool result is `379/640` answer and `362/640` exact. This is promising, but rendered proof-pool construction remains external, so it is the next route rather than a final bridge-free/direct generation claim.

## Repeated Lessons

1. Target format dominates scale. Narrow keys, compact proof payloads, and minimal selectors repeatedly move the parameter threshold more than adding width.
2. Deterministic filters are useful runtime contracts but must be separated from pure neural KBPP claims.
3. Collision gates are mandatory. Unique row ids, singleton selectors, and answer leakage can create false KBPP wins.
4. Binding is the bottleneck. Entity, field, relation, slot, proof-edge, and source-role alignment explain most late-stage failures.
5. Frozen hidden states often lack the needed equality signal. Declared comparators and learned pair classifiers work before ordinary encoder/decoder CE internalizes the same operation.
6. Candidate ranking is much easier than direct generation. Constrained materialization works after Stage1069; plain decoder fine-tuning still fails.
7. Calibration must be honest. Many eval-oracle gains disappear under external alias-salt calibration unless the representation is side-invariant and the gate is predeclared.

## Primary References

- [Active knowledge compression research](active_knowledge_compression_research.md)
- [Stage819-1046 100M bridge research update](stage819_1046_100m_bridge_research_update.md)
- [Stage758 100M factorized binding route](stage758_100m_factorized_binding_route.md)
- [Knowledge bits per parameter](knowledge_bits_per_parameter.md)
- [Operation bits per parameter](operation_bits_per_parameter.md)
- [General KBPP benchmark spec](general_kbpp_benchmark_spec.md)
- [KBPP maximization map](kbpp_maximization_map.md)
- [Model intelligence density framework](model_intelligence_density_framework.md)
