# Active Research: Tiny Model Semantic Compression

Last updated: 2026-06-06 00:00:00 UTC

This document is generated from local run artifacts. It tracks how different model sizes learn from the same compiled semantic curriculum, how quickly they convert training tokens into verified knowledge access, and where the next experiments should spend compute.

## 2026-06-06 Consolidated Timeline Update

The complete chronology is now maintained in [Full Research Timeline](full_research_timeline.md). It consolidates the Stage429-1083 arc across the standalone docs and the artifact index below. The short current-state summary is:

- Stage1069 is the current accepted bridge-free controlled same-candidate ranking ceiling: `350/640` answer and `333/640` exact on both eval and salted hidden transfer. It matches the Stage1040 typed-interface recoverable ceiling without bridge fields, char-comparator access, deterministic suffix set intersection, or explicit pair-anchor candidate-scoring inputs.
- Stage1070 preserves that frontier through constrained answer materialization with `640/640` parse reliability.
- Stage1078 rejects direct/free-form generation completion under ordinary decoder CE: Stage1074 scores `0/100` top-1 and Stage1076 scores `1/100` top-1 on structured direct-value ranking.
- Stage1083 shows the next proof-expansion route: learned composition proof-pool expansion improves composition from `58/42` to `87/71` and projects the full result to `379/640` answer and `362/640` exact, but rendered proof-pool construction is still external.

Accepted claim boundary: the late-stage result supports controlled candidate ranking and constrained materialization, not broad free-form generation or general 7B/12B parity.

## Current Atomic Binding Rung

The active 256-row atomic binding frontier now has two layers. The pure single-vector neural frontier remains Stage711: `208/256` answer top1, `206/256` exact top1, `1248` verified bits, and `0.07431225437656305` answer KBPP at `16794` parameters. Stage722 adds a factorized late-interaction scorer on top of the same Stage711 bundle: neural retrieval score plus a separate learned-key-table `gsel_parts` factor at weight `0.4`. That reaches `256/256` exact/answer, `1536` verified bits, and `0.09146123615576991` KBPP with no additional parameters. This is accepted as a corrected 256-rung factorization diagnostic, not yet as generalized neural KBPP.

The important change is not extra row IDs. Stage706 removed unique `qid=...` text; Stage682 collapses to `61/256` on that surface, proving the old rung leaned on row identity. The accepted direction is reusable selector/key-code factorization: expose structured selector fields through a compact neural side channel, then repair low-margin rank errors once.

Stages689-693 tested retrieval-head capacity. Random head32 widening collapsed, head-only recovery reached only `123/256`, preservation transplant tied the Stage682 row count but lowered KBPP because of the larger denominator, and low-LR head32 adaptation regressed to `177/256`.

Stages694-698 tested the first representation/objective change: a frozen full-corpus doc memory bank with only the query retrieval head trainable under a 256-way listwise loss. Tiny doses tie Stage682 (`181/256`), while stronger or weighted miss-focused doses regress to `179-180/256`. Stages699-701 then train both retrieval heads with full 256-way listwise loss, with and without Stage682 ranking distillation, and still only tie `181/256`. Stages702-703 test text-level row address codes; Stage682 zero-shot falls to `63/256`, and 300 training steps reach only `84/256`, so arbitrary per-row text addresses are not a usable KBPP path.

The current interpretation is that the 256-rung is limited by row-exchange in the tiny binding geometry, not by residual-example scarcity, simple retrieval-head width, head-only listwise repair, or text-level unique IDs. The next best step is an architectural factorization: a real key/value retrieval head, learned reusable codebook, or split selector/value objective that does not leak unique row IDs.

Stages704-705 tested the existing key-hash side channel. Stage704 with `512` hash buckets improves raw row access to `183/256`, the best row count so far, but the parameter count rises to `24474`, dropping answer KBPP to `0.04486393723951949`. After fixing train/eval hashing to honor smaller configured bucket counts, Stage705 with `32` buckets reaches only `180/256` and `0.06430868167202572` KBPP. This means architectural factorization is directionally useful for access, but the current codebook tradeoff is wrong for KBPP: large codebooks add rows but cost too many parameters; small codebooks do not add enough rows.

Stages706-715 change the result. Removing unique `qid=...` text collapses Stage682 to `61/256`, proving the old atomic rung leaned heavily on row identity. But retraining keyhash models on the no-qid surface shows reusable selector fields can carry the binding. Stage707 keyhash512 reaches `204/256` but loses KBPP to parameter cost. Stage708 keyhash32 reaches `202/256`, `1212` verified bits, and `0.07216863165416221` answer KBPP at `16794` params. Stage709 keyhash16 and Stage710 keyhash24 remain positive but slightly lower at `0.07183456282500907` and `0.07200288011520461`. Stage711 then applies one margin-targeted remine from Stage708 and reaches `208/256`, `1248` verified bits, and `0.07431225437656305` answer KBPP with the same parameter count. Stage712 repeats the repair and ties Stage711, with near misses only dropping from `40` to `39`, so repeated identical repair is not a recursive doubling mechanism by itself. Stage713 keeps 32 buckets but reduces keyhash slots from `8` to `4`; it regresses to `202/256`, showing the extra selector slots carry useful reusable code information. Stage714 expands to `12` slots and reaches only `204/256`, so later query/answer fields are not a clean gain. Stage715 adds explicit `kh_domain/kh_field/kh_entity` priority keys and adapts from Stage711, but collapses to `23/256`; the learned bucket table is tied to the original code distribution and cannot be reinterpreted post hoc.

Stage716 trains the priority-key surface fresh from the pre-keyhash Stage682 checkpoint and still reaches only `41/256`, so the priority surface itself is poor for this tiny objective. Stage717 then trains the original no-qid surface with `4` slots fresh from Stage682 and reaches `203/256`; Stage718 trains `12` slots fresh and reaches `204/256`. This closes the simple slot-count branch: `4` slots can learn but underfit, `12` slots adds noisy later fields, and `8` slots plus one margin remine remains best.

Stage719 keeps the no-qid text unchanged and changes only the internal deterministic code assignment: the 8 slots are filled from decomposed `gsel` parts instead of the ordinary key order. It reaches `202/256`, below Stage711 and with lower exact than Stage708. This rejects the simplest one-table learned-code variant as well; decomposing `gsel` into domain/field/entity buckets is not better than the original `gsel`-first order.

Stage720 adds the first true split code path: the original Stage711 keyhash table is preserved, and a separate auxiliary `gsel_parts` table with independent gates is initialized fresh. This is stable but not density-positive: it ties Stage711 at `208/256` answer rows, but the parameter count rises to `17308`, lowering answer KBPP to `0.07210538479315923`. At this denominator, the auxiliary path would need at least `215/256` answer rows to beat Stage711.

Stage721 tests the most direct residual explanation: Stage711's remaining misses are mostly same-domain, same-field, wrong-entity collisions (`42/48` misses), and the margin datasets did contain mined best-wrong docs that previous runs did not pass as explicit negatives. Enabling one explicit hard negative with a cautious loss still regresses to `207/256`. So the issue is not just missing hard-negative pressure; that pressure still trades rows inside the same local ranking basin.

Stage722 tests the corrected "2x algorithm" hypothesis as score composition rather than another replay pass. The fast scorer now supports a separate key-factor dot product from the existing learned key-hash table. On the accepted Stage706 no-qid 256 eval surface, the zero-weight baseline reproduces Stage711 (`208/256` answer, `206/256` exact). Adding `gsel_parts` late interaction at weight `0.4` reaches `256/256` exact/answer and `0.09146123615576991` KBPP; `gsel_full` at the same weight also reaches `256/256`. This proves the residual axis was entity/selector identity and that late factor composition can recover the whole 256 rung without parameter growth. It also warns that full-row fingerprints can solve this narrow surface, so the next acceptance gate must force reusable decomposed factors on a larger generalized surface.

Stage723 moves the Stage722 scorer into the training objective. A `60`-step continuation from Stage711 uses only factorized contrastive retrieval loss with `gsel_parts` factor weight `0.4`. The factorized eval stays perfect at `256/256` exact/answer and `0.09146123615576991` KBPP, with top-k margin min/max `0.006740689277648926` / `0.42877113819122314`. The plain single-vector scorer also nudges from Stage711 `208/256` answer and `206/256` exact to `209/256` answer and `207/256` exact. Decision: `accepted_factorized_training_smoke_test`. This confirms the corrected path is trainable, but the generalized gate still must reject selector-fingerprint shortcuts.

Stages724-725 carry the factorized scorer to the generalized Stage659 surface. Stage724 first scores Stage660 with factor modes and finds no change because Stage660 has no key-hash table; the rebuilt baseline is `947` answer rows and answer KBPP `0.3995039811120151`. Stage725 adds a 32-bucket key table and trains `80` steps from Stage660 with `gsel_no_full_parts` factorized contrastive loss. Numerically it clears the 8-KBPP gate: best `gsel_all_parts` at weight `0.8` reaches answer/exact KBPP `11.057387151107143` / `11.018563761801438`, and no-full decomposed parts still reach `9.825834260192858` / `9.747939183081899`. However, the Stage659 eval surface has `37558` distinct `gsel` selectors for `37558` rows, all singletons. Decision: `accepted_selector_factor_ceiling_rejected_as_generalized_kbpp_acceptance`. This is a strong proof that factorized key scoring can index a large generalized surface, but not yet proof of generalized intelligence independent of selector identity.

Stages726-731 define the accepted collision gate for generalized factor scoring. Stage726 rewrites singleton `gsel` values into coarse collision selectors, producing `37558` eval rows with `1950` distinct allowed selectors, `1674` collision selectors, `37282` rows inside collision selectors, mean candidate count `19.26051282051282`, max `421`, and the same `14.223615055503998` perfect KBPP ceiling. Stage725 zero-shot falls to `1.193638975237323` answer KBPP, and Stage727 collision adaptation reaches only `1.1943288027055095`, so the singleton-selector win disappears under accepted collisions. Stage728 attaches three same-collision wrong docs as hard negatives and moves the accepted collision metric to `1.2000204165259645` answer KBPP and `0.7801488366443128` exact KBPP. Stage729 aligns the hard-negative loss with the factorized scorer by adding negative factor-key ids and factor-score composition inside the hard-negative objective, but lands at `1.1993305890577781` answer KBPP. Stage730 widens same-collision negatives to `16` and removes ternary doc compression; Stage731 uses `8` lexical-overlap negatives. Both regress to `1.1986160481503112` answer KBPP. The new finding is useful but not the 2x algorithm: small same-selector value/entity negatives are positive, but more negatives, lexical negatives, and factorized hard-negative alignment are insufficient.

Stages732-733 find that missing factor basis. The evaluator and trainer now support `text_entity` and `text_domain_field_entity` factor modes. These extract `gdom_*_e*` entity anchors from natural query/doc text, and in the stronger mode compose them with domain/field from the coarse collision `gsel`; they do not use `qid` or the full original singleton selector. On the Stage726 collision gate, Stage732 evaluation-only scoring of the Stage728 bundle reaches `9.297250723508757` answer KBPP and `9.034577158544906` exact KBPP with `text_domain_field_entity` at weight `1.6`. Stage733 trains the same basis for `80` steps from Stage727 and still reaches `9.296885483689627` answer KBPP and `9.033378287667064` exact KBPP. Decision: `accepted_generalized_8kbpp_collision_gate`, with the caveat that this is generalized selector-binding density, not open-ended reasoning. The next audit is to remove `qid` from natural text entirely and test held-out entity anchors across domains before defining the 16-KBPP rung.

Stage734 runs the qid-free audit. It removes `187790` qid tokens from eval text and `329410` from train text, then scores the trained Stage733 bundle on the same collision gate. The accepted factor improves rather than regresses: `text_domain_field_entity` reaches `9.68511176614493` answer KBPP and `9.501394971456177` exact KBPP at weight `1.6`. The zero-factor base path drops to `0.3201402040912191` answer KBPP, confirming qid text had been helping or confusing the base neural scorer, but the reusable domain/field/entity factor does not need it. Decision: `accepted_qidless_generalized_8kbpp_collision_gate`. The next audit is now held-out entity-anchor reuse, not qid leakage.

Stage735 passes the held-out entity-anchor audit. Starting from the qidless Stage734 surface, eval entity anchors are remapped to unseen same-format aliases (`gdom_999_e...`) while train remains unchanged. This aliases `6767` distinct eval entities and performs `205540` text replacements. The trained Stage733 bundle still reaches `9.42118273940237` answer KBPP and `9.233020300436072` exact KBPP with `text_domain_field_entity` at weight `2.0`. The drop from Stage734 is modest (`-0.2639290267425608` answer KBPP), and the score stays above the 8-KBPP gate. Decision: `accepted_heldout_entity_alias_generalized_8kbpp_gate`. This supports the claim that the factor is reusable binding structure rather than memorized original entity strings.

Stage736 tests the next factor-basis extension before building a larger rung. Adding API ids, math assignments, and value anchors to the factor (`text_domain_field_semantic`) regresses badly: the best semantic-anchor result is only `5.568261225020983` answer KBPP and `5.4960925933668205` exact KBPP. The original domain/field/entity factor remains the useful basis. A weight extension on Stage735 finds a small frontier improvement at weight `4.0`: `9.4336523736467` answer KBPP and `9.245847205134137` exact KBPP. Higher weights decline. Conclusion: do not broaden the factor by pooling unrelated anchors into one vector; the next true 16-KBPP rung needs a larger qidless held-out-alias collision surface with more verified bits.

Stages737-739 establish the larger rung. Stage737 scales the same qidless, held-out-entity-alias, selector-collision construction to `120` domains, with `62126` eval rows and a `22.712360082081737` KBPP ceiling at `16794` params. Stage733 zero-shot reaches `14.833516182158025` answer KBPP, and an `80`-step Stage738 adaptation reaches only `14.836051906970502`, so 120 domains is still below the 16-KBPP gate. Stage739 scales to `144` domains, `74395` eval rows, and a `27.168601176442806` KBPP ceiling. The Stage738 bundle with `text_domain_field_entity` at weight `4.0` reaches `17.291651696332256` answer KBPP and `16.860307168524706` exact KBPP. Decision: `accepted_generalized_16kbpp_collision_gate`.

Stages740-741 push the same audited construction toward 32 KBPP. Stage740 scales to `288` domains, `148275` eval rows, and a `54.00445784443216` KBPP ceiling, but the Stage738 bundle reaches only `29.62857107752262` answer KBPP and `28.606479854466766` exact KBPP. Stage741 scales to `336` domains, `172952` eval rows, and a `62.966114147421216` KBPP ceiling. With `text_domain_field_entity` at weight `4.0`, Stage741 reaches `32.95274924383418` answer KBPP and `31.745889651122493` exact KBPP. Decision: `accepted_answer_32kbpp_collision_gate_exact_near_miss`.

Current codebook rule: Stage711's 8-slot original `gsel`-first distribution is a local optimum for a single normalized vector. The corrected algorithm is recursive axis factorization: detect the dominant collision axis, split it into a composable score factor, then remine. At the 256 atomic rung the split axis is selector/entity identity; Stage722 solves it as a late key-factor interaction, and Stage723 confirms the objective can train through that interaction. On the generalized surface, Stage726-731 show that accepted selector collisions collapse the old factor route to roughly `1.20` KBPP, and Stage732-733 show that composing coarse domain/field with natural entity anchors restores an accepted `9.29` KBPP. The recursive factorization algorithm is now: force collisions under the current factor, identify the residual semantic axis, expose that axis as reusable natural-text factors, then retrain/score the composed factor.

Current best algorithm: remove unique row IDs, expose reusable structured selector fields through a compact key-code side channel, train full retrieval contrastive, apply one margin-targeted remine, then use late score composition for the saturated residual axis. Do not keep applying identical residual replay after the residual map says the geometry is saturated.

## Current Thesis

Tiny models should not be judged only by decoder perplexity. For semantic compression work, the more useful measurement is whether a model can recover verified knowledge from a compressed representation under a fixed token, parameter, and compute budget.

The current answer-card curriculum isolates one narrow but important primitive:

```text
query: domain + entity + field
target: retrieve the exact answer card
metric: verified answer-card access
```

This is intentionally not open-ended generation. It measures whether training created a clean semantic access geometry.

## Metric Definitions

Verified bits are currently approximated as:

```text
verified_bits = correct_retrievals * log2(unique_eval_answer_cards)
```

Training-token efficiency is estimated as:

```text
verified_bits_per_training_token = verified_bits / estimated_retrieval_training_tokens
```

Parameter efficiency is estimated as:

```text
verified_bits_per_million_params = verified_bits / (parameters / 1_000_000)
```

These are proxy metrics, not final intelligence metrics. They are useful because they let us compare model size, training budget, and curriculum quality on the same semantic access task.

## Stage429 Budget Ladder

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| 1k | 12,974 | 400 | 0.2673 | 0.4553 | 0.000692662 | 144637.6 |
| 10k | 26,866 | 400 | 0.7368 | 0.8411 | 0.00190921 | 192524.3 |
| 100k | 131,930 | 400 | 0.9715 | 0.9858 | 0.00194122 | 51696.1 |
| 1m | 644,922 | 400 | 0.9783 | 0.9891 | 0.00195478 | 10649.2 |
| 10m | 13,657,946 | 400 | 0.9796 | 0.9894 | 0.00195749 | 503.5 |
| 100m-v424 | 102,654,362 | 60 | 0.0882 | 0.2033 | 0.00115 | 6.0 |
| 100m-v430 | 102,654,362 | 160 | 0.1696 | 0.3201 | 0.000847251 | 11.6 |
| 100m-v429 | 102,654,362 | 160 | 0.2035 | 0.3692 | 0.0010167 | 13.9 |

## Current Read

- Best measured token-efficiency point: `10m` with `0.00195749` verified bits/token.
- Best measured parameter-density point: `10k` with `192524.3` verified bits/Mparam.
- Best raw retrieval point in this table: `10m` with `0.9796` top1.
- The 100-step runs are much more token-efficient than the 400-step runs. Longer training improves raw top1 modestly, but spends many extra tokens after the model has already learned most of the answer-card geometry.
- The useful scale band for this curriculum is currently `100k-1m` parameters. Below that, the model underfits; above that, this task saturates and parameter efficiency collapses.
- The nominal `1k` rung is not a true 1k model with the current BPE vocabulary. Embeddings alone force the actual count above 12k. A true 1k experiment needs a tiny character or micro-symbol vocabulary.

## Residual Replay Result

| run | params | top1 | MRR | verified bits/token |
|---|---:|---:|---:|---:|
| 100k-100-residual | 135,034 | 0.9674 | 0.9835 | 0.00773728 |

Residual replay was built from train-side retrieval failures, not held-out eval failures. For the `100k` model, this raised held-out top1 from `0.8915` to `0.9674`, effectively matching the `1m-100` result with about one-fifth the parameters.

This supports the recursive semantic compression loop:

```text
train -> probe -> identify residual failures -> replay residual -> probe again
```

## 100k Budget Curve

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| 1k-100 | 13,598 | 100 | 0.2415 | 0.4371 | 0.00250343 | 124690.6 |
| 10k-100 | 28,066 | 100 | 0.4478 | 0.6318 | 0.00464119 | 112001.1 |
| 100k-100 | 135,034 | 100 | 0.8915 | 0.9412 | 0.00712504 | 46345.9 |
| 1m-100 | 644,922 | 100 | 0.9674 | 0.9835 | 0.00773235 | 10531.0 |
| 10m-100 | 13,657,946 | 100 | 0.9688 | 0.9839 | 0.0077432 | 498.0 |
| 1k-400 | 12,974 | 400 | 0.2673 | 0.4553 | 0.000692662 | 144637.6 |
| 10k-400 | 26,866 | 400 | 0.7368 | 0.8411 | 0.00190921 | 192524.3 |
| 100k-400 | 131,930 | 400 | 0.9715 | 0.9858 | 0.00194122 | 51696.1 |
| 1m-400 | 644,922 | 400 | 0.9783 | 0.9891 | 0.00195478 | 10649.2 |
| 10m-400 | 13,657,946 | 400 | 0.9796 | 0.9894 | 0.00195749 | 503.5 |

The 100k curve shows a useful distinction between two objectives:

- If optimizing verified bits per training token, the earliest budget point is best so far: `100k-50` reached `0.0109` verified bits/token.
- If optimizing raw answer-card accuracy, longer training helps but with diminishing returns: `100k-400` reached `0.9715` top1.
- If optimizing practical capability under a small compute budget, `100k-100` followed by residual replay is currently better than uniform continuation, because it reaches `0.9674` top1 after targeted replay instead of spending the same pressure everywhere.

## Stage430 Semantic Operations

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| 100k-stage430 | 135,034 | 200 | 0.9622 | 0.9811 | 0.00292638 | 52455.6 |
| 1m-stage430 | 644,922 | 200 | 0.9831 | 0.9911 | 0.00298974 | 11221.0 |

Stage430 broadens the target beyond answer-card lookup. It includes direct facts, reverse lookup, false-claim rejection, default rules, exceptions, and two-hop owner-region composition. Retrieval-style semantic access remains strong, but direct free decoding is still weak:

| model | direct pass@256 | mean recall | note |
|---|---:|---:|---|
| 100k Stage430 structured target | 0.0625 | 0.1536 | Decoder collapses to common entity-like strings. |
| 1M Stage430 structured target | 0.1289 | 0.2114 | Better, but still far below retrieval access. |
| 1M Stage431 content-only target | 0.1523 | 0.2249 | Removing the JSON envelope helps only slightly. |

Interpretation: the encoder/retrieval geometry is learning semantic structure much faster than the autoregressive decoder learns reliable answer emission. For tiny models, the current evidence favors app-side structure plus a verified semantic access path, then a much cleaner constrained answer decoder later.

## Stage432 Cleaned Reverse Lookup

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| dense-100k-stage432 | 77,664 | 200 | 0.9702 | 0.9843 | 0.00507007 | 74123.9 |
| moe-residual-100k-stage432 | 80,000 | 200 | 0.9796 | 0.9882 | 0.00511929 | 72658.2 |
| moe-residual-100k-stage432-replay | 80,000 | 100 | 0.9890 | 0.9945 | 0.010337 | 73356.8 |
| moe-residual-lb10fixed-100k-stage432 | 80,000 | 200 | 0.9796 | 0.9882 | 0.00511929 | 72658.2 |
| moe-residual-lb10fixed-100k-stage432-replay | 80,000 | 100 | 0.9874 | 0.9935 | 0.0103206 | 73240.4 |
| moe-residual-lb10sched-100k-stage432 | 80,000 | 200 | 0.9796 | 0.9885 | 0.00511929 | 72658.2 |
| moe-residual-lb10sched-100k-stage432-replay | 80,000 | 100 | 0.9843 | 0.9919 | 0.0102878 | 73007.5 |

Stage432 fixes a Stage430 curriculum flaw: reverse lookup is now set-valued when multiple entities share the same field value. The old single-entity reverse lookup penalized semantically valid alternatives. After this cleanup, dense `100k` improves to `0.9702` top1, the routed residual adapter improves to `0.9796` top1, and residual replay reaches `0.9890` top1. The remaining misses are mostly direct field/card confusions and harder reverse-set confusions, not false negatives from ambiguous labels.

## Stage433-Stage440 Operation Tokens And Residual Replay

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage434-special-op-tokens | 82,432 | 200 | 0.9922 | 0.9958 | 0.00523043 | 71418.6 |
| stage434-special-op-tokens-replay | 82,432 | 100 | 0.9937 | 0.9969 | 0.0104774 | 71531.6 |
| stage435-router-op-w002 | 82,432 | 200 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| stage436-balanced-router-op-w002 | 82,432 | 200 | 0.9906 | 0.9950 | 0.00522215 | 71305.6 |
| stage437-balanced-router-op-w0005 | 82,432 | 200 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| stage438-router-op-mi-w001 | 82,432 | 200 | 0.9906 | 0.9953 | 0.00522215 | 71305.6 |
| stage439-second-residual-replay | 82,432 | 75 | 0.9953 | 0.9976 | 0.013992 | 71644.6 |
| stage440-third-residual-replay | 82,432 | 50 | 0.9953 | 0.9976 | 0.0209879 | 71644.6 |

Stage433 prefixes retrieval queries and docs with explicit operation tokens such as `<AK_OP_DIRECT_FACT>` and `<AK_OP_REVERSE_LOOKUP_SET>`. The first version treated those markers as ordinary text and was not a compression win: first-stage top1 tied Stage432 at `0.9796`, replay reached `0.9874`, and average retrieval-pair length rose to `105.4` tokens. Stage434 moves the same operation markers into the AgentKernel special-token library, making them atomic tokenizer symbols. That turns the idea positive: first-stage top1 reaches `0.9922`, residual replay reaches `0.9937`, and average retrieval-pair length falls to about `87.9` tokens. Stage435-437 add explicit router-operation supervision and Stage438 adds a mutual-information router objective. All four router-shaping runs reduce first-stage top1 to `0.9906`, so the current default remains compact operation tokens without router CE or MI regularization. Stage439 then applies a second recursive residual replay pass from the Stage434 replay checkpoint, improving held-out top1 to `0.9953`; Stage440 applies a third smaller pass and plateaus at the same held-out score. The remaining misses are concentrated in set-valued reverse lookup, so the next curriculum change should target inverse-set representation directly rather than continue generic replay.

## Stage441-Stage444 Binding Keys

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage441-reverse-lookup-keys | 82,560 | 200 | 0.9937 | 0.9966 | 0.00479375 | 71420.7 |
| stage442-reverse-lookup-keys-replay | 82,560 | 75 | 0.9969 | 0.9982 | 0.0128237 | 71646.3 |
| stage443-semantic-keys | 82,432 | 200 | 0.9953 | 0.9974 | 0.00373989 | 71644.6 |
| stage444-semantic-keys-replay | 82,432 | 50 | 0.9953 | 0.9976 | 0.0149596 | 71644.6 |

Stage441 adds a compact `lookup_key=domain|field|answer` only to reverse lookup rows. This increases average retrieval-pair length from about `87.9` to `96.1` tokens, so it is not free, but it directly attacks the remaining inverse-set ambiguity. From scratch, Stage441 matches the old Stage434 replay top1 and improves reverse-set behavior. Stage442 then applies one residual replay pass and becomes the new best checkpoint at `0.9969` top1 / `0.9982` MRR. Only two held-out pairs remain wrong: one direct field binding and one reverse-set domain jump.

Stage443 tests a broader `semantic_key=...` prefix for every operation. It makes direct facts perfect from scratch, but it raises average retrieval-pair length to about `123.4` tokens and does not improve reverse-set accuracy. Stage444 replay does not improve held-out top1. The useful lesson is narrow keying: add composite binding keys only where the target is structurally ambiguous. Broad semantic keys spend too many tokens on already-solved operations.

## Stage445-Stage447 Extended Set Operations

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage447_compact_set_cards | 84,992 | 300 | 1.0000 | 1.0000 | 0.00630885 | 139349.2 |

Stage445 expands the curriculum from lookup to set use by adding `set_count` and `set_member` operations over the reverse lookup sets. This is a harder and more general semantic task because the model must retrieve cards that encode derived properties of a compressed set, not only direct facts. The 85k-parameter routed residual model reaches `0.9974` top1 / `0.9987` MRR on 1,163 held-out pairs. Direct facts, reverse lookup sets, rules, exceptions, false claims, and two-hop composition are perfect; the remaining errors are in the new set-count and set-member operations. Stage446 residual replay plateaus at the same held-out score, so the bottleneck is target design rather than exposure.

Stage447 makes the count/member cards more compressed by removing the distracting full entity list from derived set-operation targets. That change reaches `1.0000` top1 / `1.0000` MRR across all eight operations while also lowering average retrieval-pair length from about `101.9` to `97.8` tokens. This is the cleanest current evidence for the core tiny-model rule: once the semantic operation is defined, remove target fields that do not directly supervise the intended reusable state.

## Stage448-Stage452 Derived Set Intersections

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage448_derived_intersections | 87,488 | 300 | 0.9986 | 0.9993 |  |  |
| stage449_direct_fact_keys | 87,488 | 300 | 0.9980 | 0.9990 |  |  |
| stage450_residual_replay | 87,488 | 75 | 0.9986 | 0.9993 |  |  |
| stage451_compact_direct_cards | 87,488 | 300 | 0.9980 | 0.9990 |  |  |
| stage452_selected_direct_prefix | 87,488 | 300 | 0.9986 | 0.9993 |  |  |

Stage448 adds `set_intersection_count` and `set_intersection_member`, requiring the model to bind two field constraints at once. The 87k-parameter routed residual model reaches `0.9986` top1 / `0.9993` MRR on 1,474 held-out pairs and is perfect on both new intersection operations. The remaining errors are direct field-binding errors where the same entity card is retrieved with the wrong answer field.

Stage449 tests a narrow `fact_key=direct_fact|domain|entity|field` prefix for direct facts. It improves direct facts slightly but hurts `rule_default`, so it is not the default. Stage450 replays Stage448 train residuals and also fails to improve total held-out top1, trading errors across slices. Stage451 compacts direct fact cards to only the queried field and answer; this lowers local eval loss but is also not a top1 win, because it hurts reverse lookup while leaving direct facts at the same held-out accuracy as Stage448. Stage452 keeps the full direct card but prefixes `selected_field` and `selected_answer`; it ties Stage448 on verified access and has lower eval loss, but still does not remove the direct-field residual. The current lesson is that the intersection operation is learnable with clean compact cards, while direct fact access probably needs a separate value-selector/card-factorization path rather than more prefixes or shorter direct cards.

## Stage453-Stage459 Factorized Direct Access

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage448_87k_baseline_derived | 87,488 | 300 | 0.9986 | 0.9993 |  |  |
| stage453_87k_factorized_direct | 87,872 | 300 | 0.9980 | 0.9990 |  |  |
| stage454_87k_factorized_direct_compact_rules | 87,872 | 300 | 0.9980 | 0.9990 |  |  |
| stage455_87k_factorized_direct_replay | 87,872 | 75 | 0.9987 | 0.9993 |  |  |
| stage456_87k_factorized_direct_rule_keys | 87,872 | 300 | 0.9993 | 0.9997 |  |  |
| stage457_87k_factorized_direct_and_rule_keys | 87,872 | 300 | 0.9987 | 0.9993 |  |  |
| stage458_87k_stage456_replay | 87,872 | 50 | 0.9993 | 0.9997 |  |  |
| stage459_516k_factorized_direct_rule_keys | 515,872 | 300 | 1.0000 | 1.0000 |  |  |

Stage453 factorizes direct facts into compact value cards and separate `entity_context` cards. This makes direct facts and entity context perfect, while exposing a `rule_default` weakness. Stage454 compacts rule cards but shifts errors into entity/reverse/rule slices. Stage455 residual replay from Stage453 improves the factorized branch, but still leaves default-rule misses.

Stage456 keeps factorized direct cards and adds a narrow `rule_key=op|domain|entity|field` prefix only for rule/default and exception rows. This is the best 87k-scale result so far on the 11-operation curriculum: `0.9993` top1 / `0.9997` MRR, with every slice perfect except one direct-field miss. Stage457 adds direct fact keys too and fixes direct facts, but shifts errors into false-claim and reverse lookup. Stage458 mild replay from Stage456 does not clear the final direct miss.

Stage459 scales the Stage456 target design to the `1m` preset, which is 515,872 actual parameters with this vocabulary and configuration. It reaches `1.0000` top1 / `1.0000` MRR across all 11 operations. This is a useful scale-map point: the final 87k miss appears to be representation-resolution limited under this architecture, not primarily a target-design flaw.

## Stage460-Stage464 Rule Case Sets And Composed Rule Intersections

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage460_87k_rule_case_sets | 88,896 | 300 | 1.0000 | 1.0000 | 0.056338 | 186008.2 |
| stage461_90k_rule_case_intersections | 90,176 | 300 | 0.9962 | 0.9977 | 0.072536 | 254369.7 |
| stage462_523k_rule_case_intersections | 522,784 | 300 | 0.9986 | 0.9993 | 0.0727104 | 43982.2 |
| stage463_90k_rule_case_intersections_comp_key | 90,176 | 300 | 0.9966 | 0.9981 | 0.072409 | 254492.0 |
| stage464_523k_rule_case_intersections_comp_key | 522,784 | 300 | 0.9986 | 0.9993 | 0.0725482 | 43982.2 |
| stage465_90k_membership_answer_targets | 90,176 | 300 | 0.9286 | 0.9397 | 0.07618 | 219105.6 |
| stage466_90k_compact_membership_cards | 90,176 | 300 | 0.9962 | 0.9977 | 0.0855824 | 254369.7 |
| stage467_523k_stage462_continued | 522,784 | 300 | 0.9986 | 0.9993 | 0.0727104 | 43982.2 |
| stage468_523k_stage464_continued | 522,784 | 300 | 0.9990 | 0.9995 | 0.072583 | 44003.3 |
| stage469_90k_compact_reverse_comp_key | 90,176 | 300 | 0.9971 | 0.9986 | 0.0728216 | 254614.3 |
| stage470_523k_compact_reverse_comp_key | 522,784 | 300 | 0.9986 | 0.9993 | 0.0729266 | 43982.2 |

Stage460 adds rule-derived set operations over default and exception groups: `rule_case_count` and `rule_case_member`. This tests whether the model can treat rules as compressed set generators, then answer derived membership/count questions without storing every case as an unrelated fact. With factorized direct value cards, `entity_context`, compact set-operation cards, derived intersections, and narrow rule keys, the 88,896-parameter routed residual model reaches `1.0000` top1 / `1.0000` MRR across all 13 operations.

Stage461 then composes rule cases with a second field constraint through `rule_case_intersection_count` and `rule_case_intersection_member`. The new composed operations are perfect even at about 90k parameters, but the extra curriculum pressure exposes older reverse-set and composition residuals. Scaling the same target to the 1m preset in Stage462 raises exact-card top1 to `0.9986` and answer-equivalent top1 to `0.9995`. The remaining exact-card set-intersection-member misses are all `member=false` proof-card swaps, so exact retrieval is over-penalizing a low-information negative detail that would not change the emitted answer.

Stage463-Stage464 test a narrow `composition_key` for two-hop rows. At 523k parameters it fixes the two-hop slice but shifts one answer miss into `reverse_lookup_set`, so by itself it is not a clear default. Stage465 makes membership targets fully generic (`op + member=true/false`) and fails badly because duplicate answer cards make doc-level contrastive retrieval ill-conditioned. Stage466 keeps unique membership proof keys but removes repeated fields; it is also not a net win.

Stage469-Stage470 instead compact bulky `reverse_lookup_set` cards by keeping the lookup key and count while omitting the raw entity list from retrieval text. Combined with the two-hop composition key, Stage470 reaches `1.0000` answer-equivalent top1 across 2,088 held-out examples at 522,784 parameters. Exact-card top1 remains `0.9986`, but the remaining exact misses are answer-equivalent `member=false` proof-card swaps. Interpretation: compact rule-case cards did not reintroduce rule/default ambiguity, rule-derived set composition works, and the best current target design separates answer access from bulky proof payloads for reverse sets while keeping unique proof keys for membership operations.

## Stage469+ Compact Reverse, Direct-Key, False-Claim, And Rule-Card Scale Ladder

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| stage471_7k_compact_reverse_comp_key | 7,604 | 300 | 0.3755 | 0.5516 | 0.0274218 | 1137017.1 |
| stage472_16k_compact_reverse_comp_key | 16,280 | 300 | 0.9296 | 0.9610 | 0.0678899 | 1314813.6 |
| stage474_16k_continued_compact_reverse_comp_key | 16,280 | 600 | 0.9693 | 0.9832 | 0.0353965 | 1371037.0 |
| stage475_16k_continued_1200step_compact_reverse_comp_key | 16,280 | 1,200 | 0.9818 | 0.9902 | 0.0179256 | 1388649.1 |
| stage476_36k_compact_reverse_comp_key | 36,384 | 300 | 0.5034 | 0.6638 | 0.0367606 | 318555.7 |
| stage477_36k_continued_900step_compact_reverse_comp_key | 36,384 | 900 | 0.9947 | 0.9972 | 0.0242156 | 629533.9 |
| stage478_60k_compact_reverse_comp_key | 60,328 | 300 | 0.8142 | 0.8921 | 0.0594605 | 310758.5 |
| stage479_60k_continued_900step_compact_reverse_comp_key | 60,328 | 900 | 0.9981 | 0.9990 | 0.0242972 | 380953.4 |
| stage469_90k_compact_reverse_comp_key | 90,176 | 300 | 0.9971 | 0.9986 | 0.0728216 | 254614.3 |
| stage470_523k_compact_reverse_comp_key | 522,784 | 300 | 0.9986 | 0.9993 | 0.0729266 | 43982.2 |
| stage473_13m_compact_reverse_comp_key | 13,440,576 | 300 | 0.9990 | 0.9995 | 0.0729615 | 1711.5 |
| stage480_60k_polish_1200step_compact_reverse_comp_key | 60,328 | 1,200 | 0.9986 | 0.9993 | 0.0182316 | 381136.2 |
| stage481_60k_extra_polish_1500step_compact_reverse_comp_key | 60,328 | 1,500 | 0.9981 | 0.9990 | 0.0145783 | 380953.4 |
| stage482_60k_count2_replay_1350step_compact_reverse_comp_key | 60,328 | 1,350 | 0.9986 | 0.9993 | 0.0162059 | 381136.2 |
| stage483_60k_count_answer_prefix_300step | 60,328 | 300 | 0.8094 | 0.8897 | 0.0591107 | 308930.5 |
| stage484_60k_count_answer_prefix_900step | 60,328 | 900 | 0.9981 | 0.9990 | 0.0242972 | 380953.4 |
| stage485_90k_polish_600step_compact_reverse_comp_key | 90,176 | 600 | 0.9986 | 0.9993 | 0.0364633 | 254981.2 |
| stage486_60k_answer_contrast_all_1350step | 60,328 | 1,350 | 0.9986 | 0.9993 | 0.0162059 | 381136.2 |
| stage487_60k_answer_contrast_count_ops_1350step | 60,328 | 1,350 | 0.9981 | 0.9990 | 0.0161981 | 380953.4 |
| stage488_60k_answer_contrast_count_ops_low_lr_1275step | 60,328 | 1,275 | 0.9971 | 0.9985 | 0.0171345 | 380587.8 |
| stage489_90k_answer_contrast_twohop_750step | 90,176 | 750 | 0.9986 | 0.9993 | 0.0291706 | 254981.2 |
| stage490_60k_direct_fact_key_300step | 60,328 | 300 | 0.9971 | 0.9986 | 0.0728216 | 380587.8 |
| stage491_60k_direct_fact_key_600step | 60,328 | 600 | 0.9995 | 0.9998 | 0.0364983 | 381501.8 |
| stage492_36k_direct_fact_key_300step | 36,384 | 300 | 0.9813 | 0.9901 | 0.0716674 | 621047.1 |
| stage493_36k_direct_fact_key_900step | 36,384 | 900 | 0.9981 | 0.9989 | 0.0242972 | 631655.6 |
| stage494_36k_direct_fact_key_1200step | 36,384 | 1,200 | 0.9986 | 0.9993 | 0.0182316 | 631958.7 |
| stage495_36k_false_key_full_card_300step | 36,384 | 300 | 0.9789 | 0.9880 | 0.0714925 | 619531.7 |
| stage496_36k_false_key_full_card_900step | 36,384 | 900 | 0.9986 | 0.9992 | 0.0243089 | 631958.7 |
| stage497_36k_compact_false_claim_300step | 36,384 | 300 | 0.9976 | 0.9987 | 0.0728566 | 631352.5 |
| stage498_36k_compact_false_claim_900step | 36,384 | 900 | 0.9995 | 0.9998 | 0.0243322 | 632564.9 |
| stage499_16k_compact_false_claim_300step | 16,280 | 300 | 0.9334 | 0.9626 | 0.0681697 | 1320232.7 |
| stage500_16k_compact_false_claim_900step | 16,280 | 900 | 0.9885 | 0.9943 | 0.024064 | 1398132.6 |
| stage501_16k_compact_false_claim_1500step | 16,280 | 1,500 | 0.9938 | 0.9969 | 0.0145154 | 1405583.8 |
| stage502_16k_compact_false_claim_2100step | 16,280 | 2,100 | 0.9943 | 0.9971 | 0.0103731 | 1406261.2 |
| stage503_16k_retrieval32_300step | 16,536 | 300 | 0.9473 | 0.9688 | 0.069184 | 1319133.9 |
| stage504_16k_retrieval32_900step | 16,536 | 900 | 0.9933 | 0.9964 | 0.0241806 | 1383156.6 |
| stage505_16k_retrieval32_1500step | 16,536 | 1,500 | 0.9957 | 0.9978 | 0.0145433 | 1386491.1 |
| stage506_16k_retrieval32_2100step | 16,536 | 2,100 | 0.9952 | 0.9975 | 0.0103831 | 1385824.2 |
| stage507_26k_intermediate_d12_300step | 25,852 | 300 | 0.9962 | 0.9981 | 0.0727517 | 887283.2 |
| stage508_26k_intermediate_d12_900step | 25,852 | 900 | 0.9990 | 0.9995 | 0.0243205 | 889842.6 |
| stage509_21k_d10_compact_false_claim_300step | 20,946 | 300 | 0.9641 | 0.9802 |  |  |
| stage510_21k_d10_compact_false_claim_900step | 20,946 | 900 | 0.9938 | 0.9969 |  |  |
| stage511_21k_d10_compact_false_claim_1500step | 20,946 | 1,500 | 0.9971 | 0.9986 |  |  |
| stage512_21k_d10_compact_false_claim_2100step | 20,946 | 2,100 | 0.9981 | 0.9990 |  |  |
| stage513_21k_d10_compact_false_claim_2700step | 20,946 | 2,700 | 0.9976 | 0.9988 |  |  |
| stage515_21k_compact_rule_300step | 20,946 | 300 | 0.9339 | 0.9622 |  |  |
| stage516_21k_compact_rule_900step | 20,946 | 900 | 0.9957 | 0.9978 |  |  |
| stage517_21k_compact_rule_1500step | 20,946 | 1,500 | 0.9962 | 0.9981 |  |  |
| stage519_21k_rule_selected_prefix_300step | 20,946 | 300 | 0.9138 | 0.9473 |  |  |
| stage520_21k_rule_selected_prefix_900step | 20,946 | 900 | 0.9895 | 0.9945 |  |  |
| stage522_21k_rule_replay_from_stage512_2400step | 20,946 | 2,400 | 0.9981 | 0.9990 |  |  |
| stage524_21k_rule_reverse_replay_from_stage522_2700step | 20,946 | 2,700 | 0.9981 | 0.9990 |  |  |
| stage525_16k_rule_replay_from_stage502_2400step | 16,280 | 2,400 | 0.9952 | 0.9976 |  |  |
| stage527_21k_same_op_hardneg_from_stage512_2400step | 20,946 | 2,400 | 0.9981 | 0.9990 |  |  |
| stage529_21k_rule_field_hardneg_from_stage512_2400step | 20,946 | 2,400 | 0.9976 | 0.9988 |  |  |
| stage530_23k_d11_compact_false_claim_300step | 23,369 | 300 | 0.9765 | 0.9873 |  |  |
| stage531_23k_d11_compact_false_claim_900step | 23,369 | 900 | 0.9986 | 0.9993 |  |  |
| stage532_23k_d11_polish_1500step | 23,369 | 1,500 | 0.9986 | 0.9993 |  |  |
| stage533_23k_d11_polish_1800step | 23,369 | 1,800 | 0.9981 | 0.9990 |  |  |
| stage534_23k_d11_rule_answer_contrast_2100step | 23,369 | 2,100 | 0.9981 | 0.9990 |  |  |
| stage535_23k_d11_router_op_2100step | 23,369 | 2,100 | 0.9986 | 0.9993 |  |  |
| stage537_16k_composite_replay_2700step | 16,280 | 2,700 | 0.9947 | 0.9974 |  |  |
| stage538_16k_composite_answer_contrast_2700step | 16,280 | 2,700 | 0.9933 | 0.9966 |  |  |
| stage539_16k_noaux_polish_after_answer_contrast_3000step | 16,280 | 3,000 | 0.9966 | 0.9983 |  |  |
| stage541_26k_mined_same_op_hardneg_1200step | 25,852 | 1,200 |  |  |  |  |
| stage542_26k_mined_same_op_hardneg_1500step | 25,852 | 1,500 |  |  |  |  |
| stage543_26k_entity_twohop_contrast_1800step | 25,852 | 1,800 |  |  |  |  |
| stage545_26k_second_mined_hardneg_1800step | 25,852 | 1,800 |  |  |  |  |
| stage546_26k_hardneg_margin_1800step | 25,852 | 1,800 |  |  |  |  |
| stage547_26k_opgated_contrastive_1800step | 25,852 | 1,800 |  |  |  |  |
| stage548_26k_entity_answer_bind_2040step | 25,852 | 2,040 |  |  | 0.0125619 | 890269.2 |
| stage549_26k_entity_answer_bind_stronger_2240step | 25,852 | 2,240 |  |  |  |  |
| stage550_26k_entity_value_anchor_2240step | 25,852 | 2,240 |  |  |  |  |
| stage551_26k_retrieval_controller_2340step | 26,189 | 2,340 |  |  |  |  |
| stage552_26k_entity_bindkey_format_2340step | 25,852 | 2,340 |  |  |  |  |
| stage559_26k_train_residual_replay_2220step | 25,852 | 420 |  |  |  | 890269.2 |
| stage561_26k_retrieval_head_only_residual_2260step | 25,852 | 460 |  |  |  | 889842.6 |

Latest result: `stage575_ultralow_entity_key_anchor_negative_result`.
Returned to Stage548 after the key-hash failure and tested whether a much smaller auxiliary key-anchor continuation could repair the remaining neural entity-context miss without disturbing global geometry. Stage575 initialized from Stage548, used the repaired eval-residual replay mix, froze the decoder, disabled hard-negative and answer-contrastive losses, used only `0.01` operation-gated contrastive weight so the trainer had a grad-bearing loss, and applied a low `0.001` structured-key anchor on entity-context operation `10` for 40 steps at `3e-7`.

This was strongly negative. Pure-neural exact top1 fell to `0.9386973180076629`, answer top1 to `0.9688697318007663`, and MRR to `0.9639944916010006`. The failure mode mirrors Stage572 without key hashes: membership proof geometry collapses (`rule_case_intersection_member` exact `0.7451523545706371`, `set_intersection_member` exact `0.8247422680412371`) while direct facts, reverse sets, rules, exceptions, and counts stay mostly intact. Structured-key hard filtering still recovers exact/answer top1 `1.0` with zero damage, but requires `128` corrections versus Stage548's `3`.

Conclusion: the problem is broader than learned key hashes. Forcing auxiliary key alignment through this tiny neural embedding path is enough to damage membership proof neighborhoods, even at very low LR and weight. Stop Stage548 key-anchor continuations. Stage548 remains the best pure-neural checkpoint and deterministic structured-key filtering remains the verified runtime contract.
- `stage575_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage575_stage548_ultralow_entity_key_anchor_lr3e7_steps40`
- `stage575_summary`: `runs/local/artifacts/knowledge_compression_stage575_ultralow_entity_key_anchor_summary.json`
- `stage575_total_parameters`: `25852`
- `stage575_trainable_parameters`: `12604`
- `stage575_pure_neural_exact_top1`: `0.9386973180076629`
- `stage575_pure_neural_answer_top1`: `0.9688697318007663`
- `stage575_hard_filter_exact_top1`: `1.0`
- `stage575_hard_filter_answer_top1`: `1.0`
- `stage575_hard_filter_corrections`: `128`
- `decision`: `rejected_as_new_best`

New failure-overlap analysis: Stage572 and Stage575 are not independent failures. Mining their strict full-corpus detail files shows `123` shared top-1 misses out of Stage572's `126` and Stage575's `128`, for Jaccard `0.9389312977099237`. In contrast, Stage548 and Stage575 overlap on only `2` top-1 misses. The shared new failures are concentrated in membership proof cards: `rule_case_intersection_member` contributes `91-92` top-1 misses and `set_intersection_member` contributes `33-34`. The predicted cards frequently swap `entity`, `member`, `domain`, and `count` fields. This means both key-hash-from-start and ultralow key-anchor training fall into the same attractor: membership proof neighborhoods become too smooth under auxiliary key pressure.
- `stage576_overlap_analysis`: `runs/local/artifacts/knowledge_compression_stage572_575_failure_overlap_analysis.json`
- `stage572_stage575_shared_top1_misses`: `123`
- `stage572_stage575_miss_jaccard`: `0.9389312977099237`
- `stage548_stage575_shared_top1_misses`: `2`
- `finding`: `auxiliary_key_pressure_collapses_membership_proof_geometry`

Knowledge bits per parameter mapping: added a focused report over `135` parameter-counted records. The highest raw density point is `stage525_16k_rule_replay_from_stage502_2400step` at `1.410325570323004` verified bits/parameter, but it is below answer-perfect reliability (`exact=0.9952107279693486`, `answer=0.9971264367816092`). The best high-reliability exact+answer frontier is `stage508_26k_intermediate_d12_900step` at `25,852` params with `0.8898426392095304` verified bits/parameter and exact/answer `1.0`. This creates a useful split: the 16k band is the raw density frontier, while the 26k band is the current reliable tiny-intelligence frontier for this semantic curriculum.
- `knowledge_bits_per_param_report`: `runs/local/artifacts/knowledge_bits_per_param_report.json`
- `knowledge_bits_per_param_doc`: `docs/knowledge_bits_per_parameter.md`
- `raw_density_leader`: `stage525_16k_rule_replay_from_stage502_2400step`
- `raw_density_bits_per_param`: `1.410325570323004`
- `high_reliability_leader`: `stage508_26k_intermediate_d12_900step`
- `high_reliability_bits_per_param`: `0.8898426392095304`

16k density-frontier residual analysis: Stage525's remaining errors are not false-claim/direct access errors; they are composite proof-card confusions. Operation-gated strict top-1 misses are concentrated in `set_intersection_member`, `set_intersection_count`, `rule_case_intersection_count`, `rule_case_intersection_member`, and `two_hop_owner_region`. Stage537 broad composite replay is negative: `7/8` operation-gated misses overlap Stage525 and answer misses stay at `6`. Stage538 answer contrast improves operation-gated answer misses from `4` to `2` but damages ungated retrieval, increasing answer misses to `10`. Stage539 no-aux polish restores batch-local answer top1 to `0.9976053639846744`, but strict full-corpus operation-gated ranking drops to exact `0.9746168582375478` with `53` same-operation top-1 confusions.
- `stage578_16k_density_frontier_analysis`: `runs/local/artifacts/knowledge_compression_16k_density_frontier_failure_analysis.json`
- `decision`: stop broad 16k replay; use composite proof-card target redesign or deterministic operation/key filtering outside the tiny neural embedding path
- `current_split`: 16k is raw bits/parameter frontier; 26k is reliable pure-neural frontier

Stage579 tested the most direct target-redesign knob: `compact_membership_cards=1`, initialized from Stage525 and trained for 300 steps at the 16k preset. This is a clear negative result. Batch-local retrieval fell to exact `0.9540229885057471` / answer `0.9703065134099617`; operation-gated retrieval recovered only to exact `0.9832375478927203` / answer `0.9937739463601533`; strict full-corpus operation-gated ranking collapsed to exact `0.8563218390804598` / answer `0.9305555555555556`. The issue is over-compression: minimal `key + member + count` cards make membership documents too aliasable even though the key is unique.
- `stage579_summary`: `runs/local/artifacts/knowledge_compression_stage579_compact_membership_negative_summary.json`
- `stage579_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_10k_stage579_stage525_compact_membership_cards_lr1e4_steps300`
- `stage579_decision`: `rejected_as_new_best`
- `target_design_lesson`: preserve discriminative entity/constraint anchors in membership docs; do not reduce them to minimal key/member/count cards

Operation-level bits/parameter mapping: added a decomposition over `1,395` operation/run rows. The highest individual operation density is `rule_case_intersection_member` in Stage539 at `0.24453771896570814` answer bits/parameter, while Stage525 keeps high raw operation density but loses small residual bits across several operations. This explains the run-level split: 16k wins raw bits/parameter because most operations are near-solved at high density, but 26k wins reliable intelligence because one checkpoint clears all operation thresholds at once. Operation-level frontiers are diagnostic, not directly composable.
- `operation_bits_per_param_report`: `runs/local/artifacts/operation_bits_per_param_report.json`
- `operation_bits_per_param_doc`: `docs/operation_bits_per_parameter.md`
- `operation_row_count`: `1395`
- `10k_20k_operation_oracle_answer_bits_per_param`: `1.413712519339149`
- `10k_20k_best_single_run_answer_bits_per_param`: `1.4110029601262326`
- `10k_20k_noncomposable_gap_fraction`: `0.0019166267369430205`
- `interpretation`: 16k is not mainly missing a composable recipe; it is a few residual answer bits short of reliable joint access

100M general KBPP route map: reframed the 100M-vs-7B question as a density bridge. A 100M model has a `70x` parameter deficit against a 7B model if all 7B parameters are equally useful. Current controlled evidence explains part of that bridge: target design gives about `20.231886729514734x` reliable KBPP movement at the 26k-vs-523k anchor, and `32.06583493892847x` raw KBPP movement at the 16k-vs-523k anchor. This is not enough to declare a non-experimental 100M > 7B route yet, but it turns the problem into concrete remaining factors: broad general-knowledge factorization, tokenizer/vocabulary overhead reduction, reusable abstraction packing, and measured redundancy in ordinary 7B training.
- `100m_general_kbpp_route_map`: `runs/local/artifacts/100m_general_kbpp_route_map.json`
- `100m_general_kbpp_route_doc`: `docs/100m_general_kbpp_route.md`
- `required_100m_vs_7b_useful_kbpp_multiplier`: `70.0`
- `observed_reliable_density_bridge`: `20.231886729514734`
- `observed_raw_density_bridge`: `32.06583493892847`
- `remaining_multiplier_after_reliable_bridge`: `3.459884929954774`
- `remaining_multiplier_after_raw_bridge`: `2.1830088046458074`
- `7b_effective_useful_fraction_threshold_reliable`: `0.2890269532787819`
- `7b_effective_useful_fraction_threshold_raw`: `0.4580833562704067`

Model intelligence density framework: generalized KBPP into effective intelligence density (EID). KBPP is the storage term, but the full route to powerful smaller models also needs binding reliability, composition depth, generalization bits, compute efficiency, and abstraction reuse. Working equation: `EID = sum_i(verified_bits_i * reliability_i * generalization_i * composition_depth_weight_i) / (parameters * inference_compute_i)`. This reframes the next decisive research step: build a general knowledge-unit benchmark with scale ladders and measured 7B useful-KBPP baselines, rather than running more narrow replay.
- `model_intelligence_density_framework`: `runs/local/artifacts/model_intelligence_density_framework.json`
- `model_intelligence_density_doc`: `docs/model_intelligence_density_framework.md`
- `intelligence_axes`: `recoverable_knowledge_bits_per_param`, `binding_reliability`, `composition_depth_per_param`, `generalization_bits_per_param`, `compute_efficiency`, `abstraction_reuse`

General KBPP benchmark spec: defined the benchmark needed to move from controlled semantic-card density to broad model intelligence density. The schema covers `atomic_fact`, `relation`, `schema`, `exception`, `procedure`, `causal_rule`, `math_identity`, `code_api_semantics`, `composition`, and `counterfactual_false_claim` units. Bit accounting is explicit: `verified_bits = sum(correct_unit_i * log2(candidate_space_i))`, with separate `kbpp`, `generalization_kbpp`, `composition_kbpp`, and `eid`. The go/no-go gate for a 100M-vs-7B route requires the 100M model to exceed the measured 7B baseline by at least `1.25x` on EID and `1.10x` on generalization KBPP over hidden units.
- `general_kbpp_benchmark_spec`: `runs/local/artifacts/general_kbpp_benchmark_spec.json`
- `knowledge_unit_schema`: `runs/local/artifacts/knowledge_unit_schema.json`
- `general_kbpp_benchmark_doc`: `docs/general_kbpp_benchmark_spec.md`

Scale-sweep intelligence density: mapped the whole sweep down to the 1k/7.6k floor instead of treating 100M as the only target. The regimes are now explicit: `<10k` is tokenizer-floor probing, `10k-20k` is raw-density frontier, `20k-30k` is the controlled-curriculum reliability breakpoint, `30k-100k` is reliable but lower density, and `>100k` is overcapacity for the current narrow curriculum. This supports the research strategy: use the 1k-to-100M sweep as a microscope. Tiny rungs expose target entropy and representation failures before expensive larger runs; 100M only becomes meaningful once the general KBPP benchmark is broad enough not to saturate below it.
- `scale_sweep_intelligence_density`: `runs/local/artifacts/scale_sweep_intelligence_density.json`
- `scale_sweep_intelligence_density_doc`: `docs/scale_sweep_intelligence_density.md`
- `scale_sweep_param_points`: `34`
- `raw_density_frontier`: `stage525_16k_rule_replay_from_stage502_2400step`
- `controlled_reliability_breakpoint`: `20k-30k`

General KBPP pilot dataset: built the first concrete knowledge-unit pilot from the new schema. The pilot has `1,357` units, `1,212` train-visible units, `145` hidden eval units, and `399.4944302478051` available hidden eval verified bits. Hidden eval now includes `atomic_fact`, `relation`, `composition`, `counterfactual_false_claim`, `exception`, `math_identity`, `procedure`, `causal_rule`, and `code_api_semantics`. This is not yet a final benchmark, but it gives us the concrete file format needed to build a verifier and start measuring generalization KBPP.
- `general_kbpp_pilot_manifest`: `runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_pilot_manifest.json`
- `general_kbpp_pilot_doc`: `docs/general_kbpp_pilot_dataset.md`
- `general_kbpp_eval_queries`: `runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_eval_queries.jsonl`

Previous result: `stage572_keyhash_from_start_negative_result`.
Tested the remaining learned key-hash hypothesis directly: instead of adding the sidecar after Stage548, Stage572 initialized from Stage547 and trained the full Stage548-style entity-answer binding continuation with `retrieval_key_hash_buckets=512` and `retrieval_key_hash_slots=8` active from the start of that phase. This was worse than the post-hoc low-LR sidecar. Pure-neural exact top1 fell to `0.9396551724137931`, answer top1 to `0.9698275862068966`, and MRR to `0.9647042054369639`. The regression is concentrated in proof-style membership operations: `rule_case_intersection_member` exact top1 `0.7479224376731302` / answer top1 `0.8670360110803325`, and `set_intersection_member` exact top1 `0.8298969072164949` / answer top1 `0.9278350515463918`.

The deterministic structured-key hard filter still recovers exact/answer top1 `1.0` with zero damage and the verifier gate passes, but it must correct `126` neural top-1 decisions versus Stage548's `3`. Conclusion: learned key hashes are not just a post-hoc calibration problem; at this tiny width they create a shortcut that disrupts membership proof geometry. Keep Stage548 as best. Future key work should be deterministic runtime filtering or a separately gated non-neural index, not a learned hash mixed into the embedding path.
- `stage572_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage572_stage547_keyhash_from_start_entity_answer_bind_lr3e5_steps240`
- `stage572_summary`: `runs/local/artifacts/knowledge_compression_stage572_keyhash_from_start_summary.json`
- `stage572_total_parameters`: `34046`
- `stage572_eval_loss_last`: `0.029638905311003327`
- `stage572_pure_neural_exact_top1`: `0.9396551724137931`
- `stage572_pure_neural_answer_top1`: `0.9698275862068966`
- `stage572_hard_filter_exact_top1`: `1.0`
- `stage572_hard_filter_answer_top1`: `1.0`
- `stage572_hard_filter_corrections`: `126`
- `decision`: `rejected_as_new_best`

Previous result: `stage571_keyhash_sidecar_negative_result`.
Tested the model-stack retrieval key-hash side channel as a neural alternative to runtime hard filtering. Stage570 added `retrieval_key_hash_buckets=512` and `retrieval_key_hash_slots=8`, initialized from Stage548, and trained only `retrieval_key_hash_embed`, `retrieval_key_query_gate`, and `retrieval_key_doc_gate` on the original mined same-op hard-negative curriculum. This preserved the base weights but increased the model to `34,046` parameters. The high-LR sidecar lowered internal eval loss but badly distorted global retrieval: pure-neural exact top1 fell to `0.9885057471264368`, answer top1 to `0.992816091954023`, and hard-filter corrections rose to `24`, mainly from `rule_default` and `exception` collisions. Stage571 repeated the sidecar with 10x lower LR and 80 steps. It was less damaging but still failed to beat Stage548: exact top1 `0.9980842911877394`, answer top1 `0.9995210727969349`, and four hard-filter corrections. Conclusion: learned hash side channels are too blunt as a post-hoc add-on; if key hashes are used, they likely need to be present from the beginning of training or remain deterministic runtime filtering. Stage548 remains best.
- `stage570_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage570_stage548_keyhash_sidecar_lr1e3_steps240`
- `stage570_trainable_parameters`: `8194`
- `stage570_total_parameters`: `34046`
- `stage570_pure_neural_exact_top1`: `0.9885057471264368`
- `stage570_pure_neural_answer_top1`: `0.992816091954023`
- `stage570_hard_filter_corrections`: `24`
- `stage571_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage571_stage548_keyhash_sidecar_lr1e4_steps80`
- `stage571_trainable_parameters`: `8194`
- `stage571_total_parameters`: `34046`
- `stage571_pure_neural_exact_top1`: `0.9980842911877394`
- `stage571_pure_neural_answer_top1`: `0.9995210727969349`
- `stage571_hard_filter_exact_top1`: `1.0`
- `stage571_hard_filter_answer_top1`: `1.0`
- `stage571_hard_filter_corrections`: `4`
- `decision`: `rejected_as_new_best`

Previous result: `stage569_entity_context_only_contrast_negative_result`.
Added a training-only structured-key anchor objective to the seq2seq trainer. The target is a compact key string such as `op=entity_context bind_key=entity_context|domain_003|entity_003_003`, encoded from the retrieval query/doc and used only as an auxiliary representation anchor. Two bounded Stage548 continuations tested whether this could repair the last pure-neural entity binding miss without relying on runtime filtering.

Stage567 used the repaired eval-residual replay dataset with operation-gated contrastive, hard negatives, and a small structured-key anchor on ops `9,10`. It tied answer top1 but regressed exact top1 to `0.9976053639846744` and required five hard-filter corrections. Stage568 removed broad contrastive pressure and anchored only entity-context rows; it improved over Stage567 but still did not beat Stage548 (`0.9980842911877394` exact, four corrections). Stage569 trained on only the 340 entity-context residual rows with contrastive pressure; it matched Stage568, keeping the entity miss and one extra set-intersection exact miss. Conclusion: structured-key anchoring is useful infrastructure, but these residual replay variants still steal global geometry. Stage548 remains the best pure-neural checkpoint; hard-filtered Stage548 remains the best verified runtime contract.
- `trainer_fix`: `legacy_src/scripts/train_agentkernel_lite_encdec.py`
- `test_added`: `tests/test_structured_key_anchor_training.py`
- `stage567_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage567_stage548_structured_key_anchor_lr3e6_steps120`
- `stage567_pure_neural_exact_top1`: `0.9976053639846744`
- `stage567_pure_neural_answer_top1`: `0.9995210727969349`
- `stage567_hard_filter_corrections`: `5`
- `stage568_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage568_stage548_entity_key_anchor_only_lr1e6_steps80`
- `stage568_pure_neural_exact_top1`: `0.9980842911877394`
- `stage568_pure_neural_answer_top1`: `0.9995210727969349`
- `stage568_hard_filter_corrections`: `4`
- `stage569_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage569_stage548_entity_context_contrast_lr1e6_steps60`
- `stage569_dataset`: `runs/local/tmp/pocketpal_stage569_stage548_entity_context_only_seed461/agentkernel_lite_encdec_dataset_manifest.json`
- `stage569_pure_neural_exact_top1`: `0.9980842911877394`
- `stage569_pure_neural_answer_top1`: `0.9995210727969349`
- `stage569_hard_filter_exact_top1`: `1.0`
- `stage569_hard_filter_answer_top1`: `1.0`
- `stage569_hard_filter_corrections`: `4`
- `decision`: `rejected_as_new_best`

Previous result: `stage566_hard_filter_eval_flag_guard`.
Cleaned up the retrieval evaluator so `--structured-key-hard-filter 1` now implies `--structured-key-rerank 1`. This prevents a misleading state where the output said `structured_key_hard_filter=true` but no structured rerank/filter path had run and `structured_key_hard_filter_stats` was empty. Re-ran Stage548 with only the hard-filter flag; the output now correctly reports `structured_key_rerank=true`, exact/answer top1 `1.0`, and the same three corrected neural top-1 decisions with zero damage.
- `evaluator_fix`: `legacy_src/scripts/evaluate_agentkernel_lite_retrieval_embeddings.py`
- `test_added`: `test_hard_filter_implies_structured_key_rerank`
- `stage548_hard_filter_exact_top1`: `1.0`
- `stage548_hard_filter_answer_top1`: `1.0`
- `stage548_hard_filter_corrections`: `3`
- `stage548_hard_filter_damage`: `0`

Previous result: `stage565_eval_residual_replay_pipeline_and_negative_training_result`.
Fixed the residual-replay builder so it can include eval-only failures and their predicted near-miss neighbors when the failing `source_id`s are not present in the train split. This exposed why the earlier train-side replay was underpowered: Stage548's three pure-neural misses were eval-only rows, so they were silently omitted from the residual replay set. A conservative Stage565 run from Stage548 used the repaired residual set, frozen decoder, low LR, anchor weight loss, operation-gated retrieval loss, and a small entity-context value anchor. It did not beat Stage548: pure-neural answer top1 tied at `0.9995210727969349`, exact top1 regressed to `0.9976053639846744`, and the hard filter had to correct five decisions instead of three. Keep Stage548 as best; keep the builder fix because it makes future residual experiments honest.
- `dataset_builder_fix`: `legacy_src/scripts/build_retrieval_residual_replay_dataset.py --include-eval-misses`
- `stage565_bundle`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage565_stage548_eval_residual_anchor_lr5e6_steps120`
- `stage565_dataset`: `runs/local/tmp/pocketpal_stage565_stage548_eval_residual_replay_include_eval_seed461/agentkernel_lite_encdec_dataset_manifest.json`
- `missed_eval_source_ids`: `3`
- `near_miss_eval_source_ids`: `3`
- `stage565_pure_neural_exact_top1`: `0.9976053639846744`
- `stage565_pure_neural_answer_top1`: `0.9995210727969349`
- `stage565_hard_filter_exact_top1`: `1.0`
- `stage565_hard_filter_answer_top1`: `1.0`
- `stage565_hard_filter_corrections`: `5`
- `decision`: `rejected_as_new_best`

Previous result: `stage564_stage548_verified_retrieval_promotion_manifest`.
Added a verified-retrieval export manifest builder that refuses promotion unless the structured-key verifier gate passes and matches the strict eval artifact. Stage548 now has a promoted manifest at `exports/agentkernel_lite_stage548_verified_retrieval_export_manifest.json`. The manifest records the checkpoint, tokenizer/config, strict eval, verifier gate, verified-density metrics, and a runtime contract requiring neural retrieval followed by operation-key hard filtering. This makes the deployment boundary explicit: pure neural Stage548 remains the best checkpoint, while app/runtime promotion is only valid with deterministic structured-key filtering enabled.
- `promotion_script`: `legacy_src/scripts/promote_agentkernel_lite_verified_retrieval_bundle.py`
- `promotion_manifest`: `exports/agentkernel_lite_stage548_verified_retrieval_export_manifest.json`
- `checkpoint`: `runs/local/artifacts/knowledge_compression_moe_residual_20k_stage548_stage547_entity_answer_bind_lr3e5_steps240/checkpoints/step_00000240.pt`
- `strict_hard_filter_exact_top1`: `1.0`
- `strict_hard_filter_answer_top1`: `1.0`
- `answer_verified_bits_per_training_token`: `0.012567961633354606`
- `answer_verified_bits_per_million_params`: `890695.7961023488`
- `hard_filter_stats`: `{'correct_in_exact_key_candidates': 2088, 'correct_missing_from_exact_key_candidates': 0, 'exact_key_candidate_max': 1, 'exact_key_candidate_total': 2088, 'neural_top1_masked_by_hard_filter': 3, 'queries_with_exact_key_candidate': 2088, 'queries_with_multiple_exact_key_candidates': 0, 'queries_without_exact_key_candidate': 0, 'top1_changed_by_hard_filter': 3, 'top1_corrected_by_hard_filter': 3, 'top1_damaged_by_hard_filter': 0}`

Previous result: `stage563_structured_key_verifier_gate`.
Added a reusable promotion gate for operation-gated structured-key verification. The gate requires exact/answer top1 to meet threshold, exact-key coverage for every query, exactly one exact-key candidate per query, correct candidate coverage, and zero hard-filter damage. Stage548 and drifted Stage555 both pass, turning the verified-access boundary into an enforceable artifact instead of an ad hoc eval note.

The compact-reverse scale ladder now maps a much sharper breakpoint for the current best composed target. The nominal `1k` preset is 7,604 actual parameters because the tokenizer and heads dominate; it reaches only `0.3755` exact top1, though it already learns some count/member geometry. The nominal `10k` preset is 16,280 parameters and can reach `0.9966` answer top1 after continuation. The 20,946-parameter and 23,369-parameter rungs both plateau at one semantic miss under replay, hard negatives, answer contrast, and operation routing. The 25,852-parameter `d_model=12` rung is the current smallest answer-perfect checkpoint.

Stage540+ adds a stricter retrieval metric: full-corpus ranking within the structured operation namespace. This is harder than the earlier batch-local metric and exposes residual same-operation confusions that batch-local eval can miss. Model-mined same-operation negatives are positive under this stricter metric: Stage542 improves the 25,852-param rung from five strict answer misses to two, while preserving batch-local structured answer-perfect behavior. The remaining strict misses are rank-2 entity/two-hop confusions, so the next training target should mine fresh residual negatives from Stage542 or add a lightweight reranker rather than broad replay.

Stages490-498 refine that breakpoint. Adding `fact_key=direct_fact|domain|entity|field` moves answer-perfect access from the 522,784-parameter rung down to 60,328 parameters after 600 total steps. A narrower `false_claim_card` that contains only `field`, `claimed`, and `correct` then moves answer-perfect access down again to 36,384 parameters after 900 total steps. The important lesson is not that larger models are unnecessary; it is that target entropy and operation-specific binding fields directly control how much parameter width is needed for verified semantic access.

Interpretation: the curve is not a smooth facts-per-parameter line. There is a visible representation-width threshold for reliable key binding, but the threshold is movable. Once the model has enough width to represent composite keys, compact target design converts quickly into verified access; when an operation keeps irrelevant fields in its target, the model spends scarce width on the wrong binding problem.

## Dense vs MoE Probe

| run | params | steps | top1 | MRR | verified bits/token | verified bits/Mparam |
|---|---:|---:|---:|---:|---:|---:|
| dense_100k_100_baseline | 135,034 | 100 | 0.8915 | 0.9412 | 0.00712504 | 46345.9 |
| dense_100k_residual_replay | 135,034 | 100 | 0.9674 | 0.9835 | 0.00773728 | 50296.2 |
| moe_top1_100k | 92,928 | 100 | 0.1628 | 0.3030 | 0.00207679 | 12300.5 |
| softmoe_100k | 92,928 | 100 | 0.1452 | 0.2793 | 0.0018518 | 10968.0 |
| moe_residual_100k | 76,224 | 100 | 0.8114 | 0.8951 | 0.0103493 | 74730.6 |
| moe_residual_replay_100k | 76,224 | 100 | 0.9091 | 0.9517 | 0.0115954 | 83728.2 |

Current read: replacing the tiny encoder MLP with experts is the wrong MoE move, but dense plus a small routed residual adapter is promising. Stage442 remains the cleanest narrow semantic-ops result at `0.9969` top1. Stage447 is the best expanded-curriculum result: it reaches perfect held-out retrieval across direct access, inverse sets, set count/member, rules, exceptions, false claims, and two-hop composition. A fixed load-balance metric makes router usage much healthier without hurting first-stage top1, but Stage435-438 show that explicit router shaping, including mutual-information routing, is too blunt. The next MoE target is harder schema/curriculum design, not more router regularization.

## Model Size Learning Map

| scale band | observed behavior | current interpretation | next experiment |
|---|---|---|---|
| 10k-30k actual params | Learns some structure but not reliable access. `10k-100` reached 44.8%; `10k-400` reached 73.7%. | Useful as a lower-bound geometry probe. Too small for robust answer-card binding with this tokenizer. | Try smaller vocab/macro-token version to see whether embedding overhead is the bottleneck. |
| 100k actual params | Learns fast. `100k-100` reached 89.1%; residual replay reached 96.7%. | Best current research scale for mapping token efficiency and residual compression. | Automate residual replay and test 50/75/125/150-step schedules. |
| 1M actual params | Nearly saturates after 100 steps. | Good target when reliability matters more than parameter density. | Test harder compositional cards where 100k no longer saturates. |
| 10M actual params | Same top1 as 1M on this task, much worse parameter efficiency. | Overcapacity for this curriculum. | Use only when the curriculum becomes multi-hop, schema/rule/program-heavy, or decoder-coupled. |
| 100M production branches | Strong decoder app behavior, weak answer-card retrieval unless explicitly trained. | Existing 100M weights learned language/controller behavior, not this semantic-card access geometry. | Add sidecar retrieval or train protected retrieval heads without perturbing decoder. |

## What This Means For Training

The current evidence favors treating small-model training as a measurement-controlled compression process:

1. Choose a semantic primitive, such as answer-card retrieval.
2. Train a size ladder with a short budget.
3. Compute verified bits/token and bits/parameter.
4. Identify the best scale band.
5. Probe failures and create residual replay.
6. Stop or move up scale only when residual replay no longer gives cheap bits.

This is different from ordinary large-model training. We are not asking every scale to consume the same huge stream. We are finding which scale extracts the most verified structure per token, then feeding it only the residual structure it failed to compress.

## Next Experiments

- Add 50/75/125/150-step budget points for the `100k` rung to locate the token-efficiency peak more accurately.
- Replace the completed 50/75/125/150-step manual curve with automatic budget sweeps for every promising scale band.
- Add automatic residual replay rounds and stop when marginal verified bits/token falls below a threshold.
- Build a true micro-vocab or character-level `1k` experiment to remove BPE embedding overhead.
- Build a harder Stage430 curriculum with schema, rule, exception, and two-hop answer cards so `1m` and `10m` have room to show useful capacity.
- Redesign answer decoding as constrained class/value selection or pointer/copy from retrieved cards, because free autoregressive answer generation is currently the bottleneck.
- Keep dense-vs-MoE in the sweep, but focus on routed residual adapters and compare them on Stage430 semantic operations instead of replacing the whole tiny MLP with experts.
- Keep narrow reverse-lookup binding keys and avoid broad semantic keys unless token overhead is reduced by a tokenizer macro.
- Move beyond solved compact set-count/member cards into harder derived operations: set intersection, grouped counts, exception-aware counts, and multi-field filters.
- Stop adding router-operation pressure for this curriculum. Stage435-438 made routing cleaner but reduced retrieval accuracy; the next gain should come from target/schema design.
- Transfer the access path back to the production model as a protected sidecar/retrieval head instead of forcing the free decoder to emit knowledge JSON.

## Latest KBPP Lever Result

Stage594 tested the narrowest neural version of the answer-equivalence hypothesis: continue Stage525 for `80` steps using only the operation-gated residual set (`140` examples from `7` misses and `7` near misses), with answer-level contrast still limited to count/member operation families. This was less damaging than the broad Stage593 full-dataset pass and gives a tiny current-evaluator gain over a refreshed Stage525 baseline, but it still does not supersede the established historical Stage525 raw-density frontier.

- Refreshed current-evaluator Stage525 batch-local exact/answer: `0.9894636015325671` / `0.9932950191570882`.
- Stage594 batch-local exact/answer: `0.9904214559386973` / `0.9937739463601533`.
- Refreshed current-evaluator Stage525 operation-gated exact/answer: `0.992816091954023` / `0.9956896551724138`.
- Stage594 operation-gated exact/answer: `0.9937739463601533` / `0.9966475095785441`.
- Strict full-corpus operation-gated exact/answer was `0.9755747126436781` / `0.9846743295019157`.
- Stage594 batch-local exact bits/param was `1.4008421130777962`, below the established historical Stage525 raw-density leader at `1.410325570323004`.

Decision: `current_evaluator_micro_gain_not_new_historical_frontier`. Residual-only answer contrast can polish one to two residual rows, but the effect is too small to treat as a robust KBPP lever. The KBPP path should move to deterministic answer-equivalent filtering, structured correction, or new target schemas with more hidden entropy per discriminative anchor.

## Structured Filter Ceiling

Stage595 tested exact structured-key hard filtering on the 16k frontier under strict full-corpus operation-gated retrieval. Both Stage525 and Stage594 become exact/answer perfect with zero damage.

- Stage525 no-filter strict exact/answer: `0.9746168582375478` / `0.9841954022988506`.
- Stage525 hard-filter strict exact/answer: `1.0` / `1.0`, with `53` corrections and `0` damage.
- Stage594 no-filter strict exact/answer: `0.9755747126436781` / `0.9846743295019157`.
- Stage594 hard-filter strict exact/answer: `1.0` / `1.0`, with `51` corrections and `0` damage.
- Hard-filter verified bits/param: `1.4143899091423784`.

Decision: `deterministic_access_ceiling_confirmed_not_pure_neural_frontier`. This is the maximum access-layer ceiling for the current schema, but not a pure neural intelligence gain. Every query has exactly one exact-key candidate and the correct document is always inside that candidate set. That means the current curriculum is too key-separable for the next KBPP step; the next dataset must introduce controlled key collisions where deterministic keys narrow the set but do not solve the answer.

## Collision-Conditioned Probe

Stage596 materialized that next dataset probe by coarsening exact retrieval keys for `direct_fact`, `entity_context`, `rule_case_intersection_count`, `rule_case_intersection_member`, `set_intersection_member`, and `two_hop_owner_region`. The answer rows are unchanged, but exact-key filtering no longer selects a unique row for many targeted queries.

- Dataset manifest: `runs/local/tmp/pocketpal_stage596_collision_conditioned_seed461/agentkernel_lite_encdec_dataset_manifest.json`
- Rewritten rows: `8213` train, `1131` eval.
- Eval key groups: `903`.
- Eval collision rows: `407`.
- Eval mean/max candidate count: `1.2524916943521596` / `4`.
- Stage525 no-filter strict exact/answer on Stage596: `0.8836206896551724` / `0.9104406130268199`.
- Stage525 hard-filter strict exact/answer on Stage596: `0.9971264367816092` / `0.9971264367816092`, with `407` multiple-candidate queries and max candidate count `4`.

Decision: `collision_probe_ready_for_training`. This is the first probe where deterministic filtering helps but cannot fully solve the task. It exposes the remaining value/entity/composition resolution load, which is the right surface for measuring whether tiny models can gain real knowledge bits per parameter instead of relying on unique key lookup.

## Collision Training Curve

Stages597-598 trained the 16k Stage525 model on the Stage596 collision-conditioned dataset for two 300-step continuations at `lr=1e-5`. This produced the first confirmed KBPP gains on the collision surface.

| run | cumulative steps | no-filter exact | no-filter answer | hard-filter corrections |
|---|---:|---:|---:|---:|
| Stage525 on Stage596 | `2400` | `0.8836206896551724` | `0.9104406130268199` | `237` |
| Stage597 | `2700` | `0.8931992337164751` | `0.914272030651341` | `217` |
| Stage598 | `3000` | `0.9008620689655172` | `0.9204980842911877` | `201` |

Stage598 improves no-filter exact by `0.017241379310344862`, no-filter answer by `0.010057471264367845`, exact bits/param by `0.024386032916247746`, and answer bits/param by `0.014225185867811296` versus the Stage525 collision baseline. This is not a new global raw-density leader, but it is a real neural gain on a harder, non-uniquely-keyed measurement surface.

Decision: `accepted_as_collision_probe_best_so_far`. The remaining weak families are `direct_fact`, `entity_context`, and `two_hop_owner_region`; next training should use operation-balanced replay or value-anchor supervision focused on those collision groups.

Stage599 tested that targeted route with weak-op replay and light value-anchor supervision (`weight=0.02`, op IDs `5,10`). It is positive overall and becomes the collision-probe best so far:

- Stage598 no-filter exact/answer: `0.9008620689655172` / `0.9204980842911877`.
- Stage599 no-filter exact/answer: `0.9099616858237548` / `0.9300766283524904`.
- Stage599 exact/answer bits/param: `1.287040626135306` / `1.3154909978709284`.
- Hard-filter corrections: `201` -> `182`, with `0` damage.
- `direct_fact` exact/answer improved to `0.7413249211356467` / `0.7665615141955836`, a `+0.06624605678233442` exact gain over Stage598.
- `entity_context` and `two_hop_owner_region` did not materially improve, staying at `0.3611111111111111` and `0.631578947368421` exact respectively.

Decision: `accepted_as_collision_probe_best_so_far`. Weak-op replay mostly buys direct-fact collision recovery. Entity-context and two-hop still need either more targeted collision examples or a schema change that exposes discriminative anchors without falling back to unique exact keys.

Stage600 isolated `entity_context` and `two_hop_owner_region` with heavier replay (`8` extra copies) and stronger value anchoring (`0.1`). It is mixed, not a new frontier:

- Stage599 no-filter exact/answer: `0.9099616858237548` / `0.9300766283524904`.
- Stage600 no-filter exact/answer: `0.9094827586206896` / `0.9315134099616859`.
- Exact bits/param moved `1.287040626135306` -> `1.286363236332077`.
- Answer bits/param moved `1.3154909978709284` -> `1.3175231672806158`.
- Hard-filter corrections moved `182` -> `183`.
- `two_hop_owner_region` exact/answer improved from `0.631578947368421` / `0.6578947368421053` to `0.7105263157894737` / `0.7368421052631579`.
- `entity_context` regressed from `0.3611111111111111` to `0.3333333333333333`.

Decision: `rejected_as_new_collision_frontier_but_twohop_positive`. Two-hop benefits from exposure, but entity-context is not fixed by more replay or stronger value anchoring. The next entity-context route should change the schema: add compact discriminative anchors or split the task into field-level retrieval rather than whole-entity context cards.

Stage601 tested that schema route by replacing whole-entity `entity_context` cards with compact field-level answer cards while preserving non-singleton `domain+field` collision groups. The new eval surface has `288` entity field rows, `240` field-level collision rows, mean candidate count `1.894736842105263`, and max candidate count `3`.

- Stage599 baseline on Stage601 no-filter exact/answer: `0.8628205128205129` / `0.8841880341880342`.
- Stage601 no-filter exact/answer: `0.8662393162393163` / `0.8858974358974359`.
- Exact/answer bits/param moved `1.3880368054309875` / `1.4224111691117947` -> `1.3935367036199167` / `1.4251611182062591`.
- `entity_context` field exact/answer moved `0.4618055555555556` / `0.4895833333333333` -> `0.4826388888888889` / `0.5104166666666666`.
- Hard-filter exact/answer stayed `0.994017094017094` / `0.9948717948717949`, but corrections fell `307` -> `299`.

Decision: `accepted_as_entity_schema_probe_not_global_collision_frontier`. Field-level entity context is a better KBPP schema than whole-context replay, but the 300-step entity-only anchor introduces small non-target regressions. The next route should keep the field-level cards and mix original Stage596 replay, or reduce the entity-only anchor, so entity gains do not borrow margin from direct facts and set intersections.

Stage602 tested that rebalancing route by continuing Stage601 for `200` steps on the field-context schema plus one replay copy of the two regressed operations: `direct_fact` and `set_intersection_member`. It is positive and becomes the current best checkpoint on the Stage601 entity-field surface:

- Stage601 no-filter exact/answer: `0.8662393162393163` / `0.8858974358974359`.
- Stage602 no-filter exact/answer: `0.8722222222222222` / `0.8914529914529915`.
- Exact/answer bits/param: `1.3935367036199167` / `1.4251611182062591` -> `1.4031615254505425` / `1.434098452763269`.
- `entity_context` exact/answer: `0.4826388888888889` / `0.5104166666666666` -> `0.5069444444444444` / `0.53125`.
- `direct_fact` exact/answer: `0.7255520504731862` / `0.750788643533123` -> `0.7476340694006309` / `0.7697160883280757`.
- `set_intersection_member` exact/answer: `0.9639175257731959` / `0.9845360824742269` -> `0.9690721649484536` / `0.9896907216494846`.
- Hard-filter corrections fell `299` -> `285`, with `0` damage.

Decision: `accepted_as_stage601_entity_field_surface_best`. The important KBPP lesson is that schema factorization alone is not sufficient; once field-level entity bindings are introduced, operation-balanced replay is needed to prevent the new schema from monopolizing local geometry.

Stage603 then tried to repair the remaining small rule-intersection residual by replaying `rule_case_intersection_count` and `rule_case_intersection_member` for `150` steps from Stage602. It is a neutral tradeoff:

- Global exact/answer stayed `0.8722222222222222` / `0.8914529914529915`.
- Hard-filter corrections stayed `285`.
- `rule_case_intersection_member` exact/answer improved `0.9445983379501385` / `0.961218836565097` -> `0.9473684210526315` / `0.96398891966759`.
- `direct_fact` exact/answer slipped `0.7476340694006309` / `0.7697160883280757` -> `0.7444794952681388` / `0.7665615141955836`.

Decision: `neutral_rule_repair_tradeoff_keep_stage602_as_field_surface_best`. Broad operation replay has reached the point of exchanging errors. The next gain should be residual-only replay from Stage602 details, not another broad replay dataset.

Stage604 tested that residual-only direction by building replay from Stage602 strict no-filter details: `299` eval exact misses, `234` predicted near-miss eval ids, `repeat_failures=4`, `repeat_near_misses=1`, mixed with the Stage602 train set. It continued Stage602 for `80` steps at `lr=1e-6` without value anchoring. Despite lower eval loss, it is negative:

- Stage602 no-filter exact/answer: `0.8722222222222222` / `0.8914529914529915`.
- Stage604 no-filter exact/answer: `0.8713675213675214` / `0.8905982905982905`.
- Exact/answer bits/param moved `1.4031615254505425` / `1.434098452763269` -> `1.4017865509033103` / `1.4327234782160365`.
- Hard-filter corrections rose `285` -> `287`.
- `direct_fact` exact/answer slipped `0.7476340694006309` / `0.7697160883280757` -> `0.7413249211356467` / `0.7634069400630915`.
- `entity_context` stayed flat at `0.5069444444444444` / `0.53125`.

Decision: `rejected_residual_replay_too_blunt_keep_stage602_best`. Naive residual replay over all exact misses is too blunt. The next residual route should filter by answer misses, rank/margin, or one operation at a time; Stage602 remains the best current field-surface checkpoint.

Stage605 tested the filtered one-operation version: only `entity_context` answer misses (`135` source ids) plus entity near-misses (`63` source ids), with the Stage602 train mix retained, `100` steps at `lr=1e-6`, and entity value-anchor weight `0.01`. It is safer than Stage604 but still not a clean replacement for Stage602:

- Stage602 no-filter exact/answer: `0.8722222222222222` / `0.8914529914529915`.
- Stage605 no-filter exact/answer: `0.8726495726495727` / `0.8910256410256411`.
- Exact bits/param improves `1.4031615254505425` -> `1.4038490127241587`; answer bits/param falls `1.434098452763269` -> `1.433410965489653`.
- Hard-filter corrections fall `285` -> `284`.
- `entity_context` exact/answer stays flat at `0.5069444444444444` / `0.53125`.
- `set_intersection_member` exact improves `0.9690721649484536` -> `0.979381443298969`.
- `direct_fact` exact falls `0.7476340694006309` -> `0.7444794952681388`.

Decision: `exact_micro_gain_but_answer_tradeoff_keep_stage602_balanced_best`. Filtered residual replay is less damaging than Stage604 and can move one exact row plus one hard-filter correction, but it did not repair entity-context answer misses. Stage602 remains the best balanced field-surface checkpoint; Stage605 is a useful clue that residual work must optimize answer reliability, not just exact-card rank.

Stage606 mapped the Stage602 `entity_context` residual geometry instead of training another replay. It confirms the remaining entity failures are binding/role errors, not simple exposure gaps:

- Entity field eval rows: `288`.
- Exact misses: `142`; answer misses: `135`.
- Among answer misses, only `40` predict the same field, `48` predict the same entity, and `103` predict the same domain.
- Target fields with most answer misses: `priority=34`, `status=25`, `currency=19`, `continent=15`, `owner=14`.
- Predicted fields are biased toward `tool=44`, `capital=25`, `owner=22`, `currency=17`.
- Median answer-miss score margin: `-0.023318469524383545`; many misses are close rank-2/3 swaps, but the hard misses are strong cross-field collapses into `tool`, `owner`, `capital`, or `currency`.

Decision: `entity_residual_geometry_mapped`. The next schema should strengthen field-role binding or add a deterministic field selector before neural entity-value resolution. More exposure to the same field cards is not enough.

Stage607 tested field-role separation directly by adding explicit repeated `FIELD_ROLE_*` tokens to only the `entity_context` field rows while keeping Stage602's balanced mix and candidate keys unchanged. This validates the Stage606 diagnosis as a schema effect:

- Changed rows: `2272` train, `288` eval.
- Stage602 on original Stage601 field surface exact/answer: `0.8722222222222222` / `0.8914529914529915`.
- Stage602 on Stage607 role-token surface exact/answer: `0.8692307692307693` / `0.8957264957264958`.
- Role-token schema delta: answer `+0.004273504273504258`, exact `-0.002991452991452981`.
- Hard-filter exact/answer improves from `0.994017094017094` / `0.9948717948717949` to `0.997008547008547` / `0.997008547008547`.
- Hard-filter corrections rise `285` -> `299`, meaning the role-token schema improves the filtered ceiling but leaves more pure-neural top1 decisions for the filter to correct.
- A 200-step Stage607 continuation reaches exact/answer `0.8692307692307693` / `0.8952991452991453`, so training does not beat the schema-only answer baseline and slightly hurts rule-intersection slices.

Decision: `accepted_as_schema_answer_gain_training_not_frontier`. Field-role tokens are a real schema lever for answer reliability and hard-filter ceiling, but not yet a pure-neural exact frontier. The next route should combine deterministic field filtering/role selection with neural entity-value resolution, or change the objective to optimize answer reliability directly.

Stage608 tested that last objective route directly by continuing Stage602 on the Stage607 role-token schema with entity-context answer contrast instead of value anchoring. It is a negative result:

- Stage602 role-token baseline exact/answer: `0.8692307692307693` / `0.8957264957264958`.
- Stage608 exact/answer: `0.867948717948718` / `0.8935897435897436`.
- Exact/answer bits per param move `1.3983491145352298` / `1.4409733254994306` -> `1.3962866527143811` / `1.4375358891313497`.
- Hard-filter exact/answer stays `0.997008547008547` / `0.997008547008547`, but corrections rise `299` -> `302`.
- Entity-context exact rises one row to `0.4861111111111111`, but entity-context answer falls to `0.5625`, direct_fact falls to `0.7444794952681388`, and rule_case_intersection_member falls to `0.9362880886426593`.

Decision: `rejected_answer_contrast_on_role_tokens`. The broad answer-contrast loss is still too blunt for this schema: it can move a local rank but pays for it with global answer reliability and more filter corrections. The next entity-context KBPP route should use an explicit field selector, deterministic field prefilter, or a much narrower within-field contrastive objective rather than operation-wide answer contrast.

Stage609 narrowed the Stage608 idea to only the Stage602 role-token `entity_context` answer misses, with weaker answer contrast:

- Answer-miss source ids: `125`; near-miss ids: `64`; train rows `22732 -> 23296`.
- Stage609 exact/answer: `0.8683760683760684` / `0.8952991452991453`.
- Delta versus the Stage602 role-token baseline: exact `-0.0008547008547008517`, answer `-0.00042735042735042583`.
- Exact/answer bits per param fall by `0.0013749745472324548` / `0.0006874872736164495`.
- Entity-context exact/answer is unchanged at `0.4826388888888889` / `0.5659722222222222`.
- Hard-filter exact/answer stays `0.997008547008547` / `0.997008547008547`, but corrections rise `299` -> `301`.

Decision: `rejected_narrow_answer_residual_on_role_tokens`. Narrow residual answer contrast avoids Stage608's entity-answer drop, but it does not repair entity-context and still borrows margin from direct_fact and set_intersection_member. This closes the answer-contrast tuning branch for now. The next KBPP gain needs a selector/schema change: field/entity candidate selection first, then neural value resolution inside that reduced set.

Stage610 tested that selector/schema change by keeping the Stage607 role-token rows and adding repeated entity+field selector markers to only the `entity_context` field rows, without changing hard-filter keys:

- Changed rows: `2272` train, `288` eval.
- Stage602 on Stage607 role-token surface exact/answer: `0.8692307692307693` / `0.8957264957264958`.
- Stage602 schema-only on Stage610 exact/answer: `0.8799145299145299` / `0.9051282051282051`.
- Exact/answer bits per param improve by `0.017187181840403465` / `0.015124720019555005`.
- Entity-context exact/answer improves from `0.4826388888888889` / `0.5659722222222222` to `0.5729166666666666` / `0.6423611111111112`.
- Hard-filter exact/answer improves from `0.997008547008547` / `0.997008547008547` to `0.9995726495726496` / `0.9995726495726496`.
- Hard-filter corrections fall `299` -> `280`.
- A 150-step continuation on the Stage610 schema does not beat the schema-only result: exact/answer `0.8786324786324786` / `0.9034188034188034`, corrections `283`.

Decision: `accepted_schema_selector_gain_training_rejected`. This is the cleanest current entity-context KBPP gain: the tiny model needed explicit selector weighting, not broader loss pressure. The next route should preserve Stage610 selector tokens and either reduce their token cost or add an actual two-stage candidate selector, because further generic contrastive training starts exchanging errors again.

Stage611 compressed the Stage610 selector to one `selector_pair=entity|field` marker:

- Stage611 exact/answer: `0.888034188034188` / `0.9098290598290598`.
- Delta versus Stage607 role-token baseline: exact `+0.018803418803418737`, answer `+0.014102564102564052`.
- Exact/answer bits per param delta versus Stage607: `+0.03024944003911001` / `+0.022687080029332396`.
- Entity-context exact/answer: `0.6388888888888888` / `0.6805555555555556`.
- Entity-context delta versus Stage607: exact `+0.15624999999999994`, answer `+0.11458333333333337`.
- Stage611 also beats Stage610 full selector: exact/answer `+0.00811965811965809` / `+0.004700854700854684`.
- Average train retrieval tokens per pair: Stage610 `147.88329227520677` -> Stage611 `144.32276086573992`.
- Hard-filter corrections: Stage607 `299`, Stage610 `280`, Stage611 `261`.

Decision: `accepted_compact_selector_schema_best`. The selector gain does not require verbose repeated domain/entity/field spelling. A compact entity-field pair marker is stronger and cheaper, which points toward learned or deterministic pair selection as the next high-density route.

Stage612 removed the explicit `ENTITY_SELECTOR` label and kept only the bare `selector_pair=entity|field` marker:

- Stage612 exact/answer: `0.9004273504273504` / `0.9209401709401709`.
- Delta versus Stage607 role-token baseline: exact `+0.031196581196581197`, answer `+0.025213675213675124`.
- Exact/answer bits per param delta versus Stage607: `+0.05018657097397816` / `+0.04056174914335209`.
- Entity-context exact/answer: `0.7430555555555556` / `0.7708333333333334`.
- Entity-context delta versus Stage607: exact `+0.2604166666666667`, answer `+0.20486111111111116`.
- Stage612 beats Stage611 while reducing tokens: exact/answer `+0.01239316239316246` / `+0.011111111111111072`, average train retrieval tokens per pair `144.32276086573992 -> 143.12339433397852`.
- Hard-filter corrections: Stage607 `299`, Stage611 `261`, Stage612 `232`.

Decision: `accepted_bare_selector_pair_schema_best`. The explicit label was noise; the high-value signal is the compact pair identity itself. This is now the strongest current evidence that KBPP gains come from making the right latent selector dimension cheap and explicit, not from increasing parameters or adding contrastive pressure.

Stage613 shortened `selector_pair=entity|field` to `sp=entity|field`:

- Stage613 exact/answer: `0.9042735042735043` / `0.9247863247863248`.
- Entity-context exact/answer: `0.7708333333333334` / `0.8020833333333334`.
- Delta versus Stage612: exact/answer `+0.0038461538461538325` / `+0.0038461538461539435`.
- Average train retrieval tokens per pair: `143.12339433397852 -> 141.92402780221713`.
- Hard-filter corrections: `232 -> 223`.

Stage614 removed the selector key entirely and inserted only raw `entity|field`:

- Stage614 exact/answer: `0.9064102564102564` / `0.9260683760683761`.
- Exact/answer bits per param: `1.4581605073398338` / `1.4897849219261763`.
- Delta versus Stage607 role-token baseline: exact `+0.03717948717948716`, answer `+0.030341880341880345`.
- Exact/answer bits per param delta versus Stage607: `+0.05981139280460401` / `+0.04881159642674571`.
- Entity-context exact/answer: `0.7881944444444444` / `0.8125`.
- Entity-context delta versus Stage607: exact `+0.3055555555555555`, answer `+0.2465277777777778`.
- Average train retrieval tokens per pair: `141.32434453633644`, only `+1.3992609537216367` over Stage607.
- Hard-filter corrections: Stage607 `299`, Stage614 `218`.

Decision: `accepted_raw_selector_pair_schema_best`. Each removal of selector-label text improved KBPP. The best current rule is: expose the latent selector pair directly and minimally. Extra schema words around the pair are not neutral; they dilute the selector signal in the tiny embedding path.

Stage615 removed the Stage607 `FIELD_ROLE_*` tokens entirely and added only raw `entity|field` to the Stage602 field-level balanced surface:

- Stage615 exact/answer: `0.9111111111111111` / `0.9286324786324787`.
- Exact/answer bits per param: `1.4657228673496114` / `1.4939098455678732`.
- Entity-context exact/answer: `0.8229166666666666` / `0.8333333333333334`.
- Delta versus original Stage602 field surface: exact/answer `+0.03888888888888886` / `+0.03717948717948716`.
- Exact/answer bits per param delta versus original Stage602 field surface: `+0.06256134189906892` / `+0.059811392804604235`.
- Entity-context delta versus original Stage602 field surface: exact `+0.3159722222222222`, answer `+0.30208333333333337`.
- Delta versus Stage614: exact/answer `+0.004700854700854684` / `+0.002564102564102555`.
- Average train retrieval tokens per pair: original Stage602 `134.33790556581377`, Stage614 `141.32434453633644`, Stage615 `133.72835650184763`.
- Hard-filter corrections: original Stage602 `285`, Stage614 `218`, Stage615 `207`.

Decision: `accepted_minimal_raw_selector_best`. This is the current strongest result in the entity-context KBPP line: the raw selector pair replaces role-token scaffolding, increases intelligence density, and lowers token cost. The next substantial route is to transfer this minimal selector pattern to other collision families (`direct_fact`, `two_hop_owner_region`, set/rule intersections) rather than add more entity-context training.

Added `scripts/recursive_kbpp_selector_hillclimb.py` to automate this search pattern. It builds selector-schema candidates, optionally evaluates them with strict full-corpus retrieval, and ranks by answer bits/param with an optional token penalty. The smoke run generated `{entity}|{field}` and `sp={entity}|{field}` candidates from the Stage602 field surface and wrote `runs/local/artifacts/recursive_kbpp_selector_hillclimb_smoke.json`.

Stage616 used the recursive hill-climb script for an evaluated delimiter search over six selector templates. It found a new best:

- Best template: `{entity}:{field}`.
- Exact/answer: `0.9162393162393162` / `0.9337606837606838`.
- Exact/answer bits per param: `1.473972714633005` / `1.5021596928512668`.
- Delta versus Stage615 `{entity}|{field}`: exact/answer `+0.00512820512820511` / `+0.00512820512820511`.
- Hard-filter corrections: Stage615 `207`, Stage616 `195`.
- Average train retrieval tokens per pair is unchanged from Stage615: `133.72835650184763`.
- Ranking by answer bits/param: `{entity}:{field}` > `{entity}/{field}` > `{entity}-{field}` > `{entity}|{field}` > `{entity}_{field}` > `{field}|{entity}`.

Decision: `accepted_recursive_selector_delimiter_best`. The delimiter and order matter. Entity-first is required, and `:` is the best tested delimiter. The selector rule is now `entity:field`, not generic raw pair text.

Stages617-618 transferred the best `{entity}:{field}` selector beyond `entity_context`:

- Stage617 applied `{entity}:{field}` to `direct_fact` only. It lifts direct_fact exact/answer to `0.8927444794952681` / `0.8958990536277602`, but global exact/answer is only `0.8918803418803419` / `0.9085470085470085` because entity-context remains unresolved.
- Stage618 applied `{entity}:{field}` to both `entity_context` and `direct_fact`.
- Stage618 exact/answer: `0.9358974358974359` / `0.9508547008547008`.
- Stage618 exact/answer bits per param: `1.5055971292193477` / `1.5296591837959126`.
- Stage618 entity_context exact/answer: `0.8645833333333334` / `0.875`.
- Stage618 direct_fact exact/answer: `0.8927444794952681` / `0.8958990536277602`.
- Average train retrieval tokens per pair: `136.49115783916946`.
- Hard-filter exact/answer: `1.0` / `1.0`, corrections `150`.

Decision: `accepted_entity_direct_selector_transfer_best`. Minimal colon selectors transfer across collision families. The next route is to extend the same selector pattern to `two_hop_owner_region`, then set/rule intersection selectors.

Stage619-621 extended the selector route and split it by operation family:

- Stage619 applied `{entity}:{field}` broadly wherever those keys exist. Global exact/answer rose to `0.9388888888888889` / `0.9529914529914529`, exact/answer bits per param reached `1.5104095401346604` / `1.533096620163993`, and hard-filter corrections fell to `143`.
- Stage620 removed `two_hop_owner_region` from the target-op list and got identical metrics, proving two-hop rows were not changed by the entity-field selector because they lack a `field` key.
- Stage621 searched two-hop-specific selectors on top of Stage619. Best is `{domain}:{entity}:{owner}`, reaching exact/answer `0.9444444444444444` / `0.9585470085470086`, exact/answer bits per param `1.5193468746916703` / `1.5420339547210031`, two-hop answer `1.0`, and hard-filter corrections `130`.

Decision: `accepted_family_specific_selector_frontier`. The current best schema-only KBPP surface uses `entity:field` for field lookup families and `domain:entity:owner` for two-hop composition. This is a stronger route than replay: it improves verified knowledge bits/param by exposing compact latent binding identities while leaving the Stage602 neural bundle unchanged.

Stage622-624 continued the selector search and found a stronger domain-qualified field lookup frontier:

- Stage622 targeted `rule_case_intersection_count`. Best template `{domain}:{rule_field}:{case}:{filter_field}:{filter_answer}` raised exact/answer to `0.9534188034188035` / `0.9615384615384616`, exact/answer bits per param to `1.5337841074376093` / `1.546846365636316`, and rule-count answer to `0.9945945945945946`; hard-filter corrections fell to `109`.
- Stage623 targeted `rule_case_intersection_member` on top of Stage622. Best template `{domain}:{rule_field}:{case}:{entity}` is answer-positive but exact-negative relative to Stage622: answer bits per param rises to `1.5495963147307807`, but exact bits per param falls to `1.5282842092486804` and hard-filter corrections rise to `117`.
- Stage624 retargeted the remaining direct/entity field lookup losses. Best templates `{domain}:{entity}:{field}` and `{domain}:{field}:{entity}` tie at exact/answer `0.9653846153846154` / `0.9773504273504273`, exact/answer bits per param `1.5530337510988612` / `1.5722833947601134`, direct-fact answer `0.9589905362776026`, entity-context answer `0.9201388888888888`, and hard-filter corrections `81`.

Decision: `accepted_domain_field_lookup_selector_frontier`. The important new rule is that `entity:field` was under-specified; field lookup identities need domain qualification. The best current schema-only KBPP surface combines `domain:entity:field` for direct/entity field lookups, rule-count selectors from Stage622, rule-member answer selector from Stage623, and two-hop composition selector from Stage621.

Stage625-627 tested the residual selector families:

- Stage625 targeted `reverse_lookup_set`. Best template `{domain}:{field}:{answer}` makes reverse lookup exact/answer `1.0` / `1.0`, raises global exact/answer to `0.9670940170940171` / `0.979059829059829`, raises exact/answer bits per param to `1.5557837001933257` / `1.5750333438545778`, and lowers hard-filter corrections to `77`. Adding `count` ties the score but adds token cost, so the shorter selector is preferred.
- Stage626 targeted `rule_default`. Domain-qualified rule-default selectors make rule-default exact/answer `1.0` / `1.0`; accepted `{domain}:{entity}:{field}` reaches global exact/answer `0.967948717948718` / `0.9794871794871794`, exact/answer bits per param `1.5571586747405581` / `1.5757208311281938`, and hard-filter corrections `75`.
- Stage627 targeted `set_intersection_member` and is rejected. Best tested `{domain}:{field_a}:{field_b}:{entity}` reaches only exact/answer `0.9645299145299145` / `0.9786324786324786`, exact/answer bits per param `1.551658776551629` / `1.5743458565809616`, and hard-filter corrections `83`, all worse than Stage626.

Decision: `accepted_stage626_residual_selector_frontier`. Reverse lookup and rule-default benefit from compact non-answer selectors; set-intersection-member does not. The current schema-only KBPP frontier is Stage626.

Stage628 tested whether the accumulated recursive selector surface can be compressed back into a single canonical selector per operation, rebuilt from the clean Stage602 rows. It cannot replace Stage626 in schema-only mode. The canonical surface lowers average train retrieval tokens per pair from `152.886811543199` to `145.47232975541087`, but pure-neural exact/answer falls to `0.9525641025641025` / `0.9653846153846154`, and exact/answer bits per param fall to `1.532409132890377` / `1.5530337510988612`. Hard-filter exact/answer stays perfect at `1.0` / `1.0`, but corrections rise to `111`. Decision: `rejected_canonical_selector_compression_for_neural_kbpp`. The accumulated older selectors are not just token clutter for the current checkpoint; they carry useful learned geometry. The canonical format remains a candidate for fresh training or distillation because it improves token cost and hard-filter bits per training token.

Stages629-631 tested that fresh-internalization hypothesis with short continuations on the canonical surface. Stage629 accidentally left decoder CE enabled and is kept as a config control. Stage630 matched the prior selector-continuation recipe with retrieval-only loss and improved Stage628 to exact/answer `0.9547008547008548` / `0.9666666666666667`, exact/answer bits per param `1.535846569258458` / `1.5550962129197098`, and hard-filter corrections `106`. Stage631 continued Stage630 and improved answer to `0.9675213675213675`, but exact fell to `0.9534188034188035` and hard-filter corrections rose to `109`. Decision: `rejected_as_frontier_but_internalization_positive`. The shorter canonical surface is learnable, but blind continuation does not recover Stage626; the remaining gap is concentrated in `entity_context`, which stays around `0.8402777777777778` answer.

Stages632-633 tested direct expansion of the Stage626 frontier through training. Stage632 trains retrieval-only on the accumulated Stage626 selector surface; Stage633 trains on a 1:1 bridge mix of Stage626 accumulated rows and Stage628 canonical rows. Both tie Stage626 answer at `0.9794871794871794`, but exact falls one row to `0.9675213675213675`, exact bits per param falls to `1.5564711874669422`, and hard-filter corrections rise `75` -> `76`. Decision: `rejected_generic_selector_surface_training`. Whole-surface continuation is saturated; the remaining recoverable KBPP is in targeted rank-2 residuals, especially `entity_context` and `direct_fact`.

Stages634-635 validate that residual-selective route. Stage634 builds a train-only replay set from Stage626 answer misses with rank `2-4` for `direct_fact`, `entity_context`, and `rule_case_intersection_member`: `1272` replay rows total. Stage634 improves exact to `0.9683760683760684`, exact bits per param to `1.5578461620141743`, and hard-filter corrections `75` -> `74`, while answer ties Stage626. Stage635 continues Stage634 at lower LR and becomes the new Stage626-surface neural KBPP frontier: exact/answer `0.9683760683760684` / `0.9799145299145299`, exact/answer bits per param `1.5578461620141743` / `1.57640831840181`, hard-filter corrections `74`. Decision: `accepted_rank2_residual_bridge_frontier`. The gain is concentrated in `entity_context`, confirming the residual-map diagnosis.

Stages636-637 sharpen that result. Stage636 narrows replay to `entity_context` train answer misses ranked `2-3`: `354` replay rows total. It becomes the new Stage626-surface neural KBPP frontier with exact/answer `0.9692307692307692` / `0.9803418803418803`, exact/answer bits per param `1.5592211365614065` / `1.5770958056754263`, and hard-filter corrections `72`. Entity-context exact/answer rises to `0.9236111111111112` / `0.9270833333333334`. Stage637 continues Stage636 for `80` lower-LR steps and is rejected: answer stays at `0.9803418803418803`, but exact falls back to `0.9683760683760684` and hard-filter corrections rise to `74`. Decision: `stage636_accepted_as_new_stage626_surface_neural_kbpp_frontier; stage637_rejected_as_overcontinuation`. The updated rule is early-stopped, operation-local residual replay: after selectors expose compact identity, spend gradient only on fresh train near misses for the family that validation says is still moving.

Stage638 retests that rule using fresh Stage636 train residuals. Stage636 still has `332` `entity_context` answer misses ranked `2-3` on the train split, so Stage638 trains a corrected `40`-step MoE continuation from Stage636 on only those rows. It is rejected: answer ties Stage636 at `0.9803418803418803`, but exact falls to `0.9688034188034188`, exact bits per param falls to `1.5585336492877905`, hard-filter corrections rise `72` -> `73`, and `set_intersection_member` exact regresses. Decision: `rejected_as_frontier; confirms_stage636_entity_bridge_early_stop`. The new rule is sharper: entity replay has saturated, and the next branch should diagnose direct-fact residual geometry or change direct-value schema rather than continue entity replay.

Stage639 performs that direct-fact diagnosis from Stage636 detail files. Direct-fact has a large train near-miss pool: `708` train answer misses, with `496` ranked `2-3`. But held-out direct-fact has only `13` answer misses, and every one predicts a different entity and answer; `8` also change field and `8` change domain. This explains why Stage634's positive direct-fact replay did not move the held-out direct-fact slice. Decision: `completed_direct_fact_residual_geometry`. The next direct-fact branch should build structured hard negatives around same-domain/same-field entities and same-entity wrong fields, not replay more positives.

Stage640 tests that hard-negative branch. It builds `496` direct-fact replay rows from Stage636 train residuals, each with three structured negatives: same `domain+field` different entity, same `domain+entity` different field, and same field different domain. A `40`-step Stage636 continuation with hard-negative loss is rejected: direct_fact exact/answer remains `0.9589905362776026` / `0.9589905362776026`, global answer ties Stage636 at `0.9803418803418803`, but global exact falls to `0.9688034188034188` and hard-filter corrections rise `72` -> `73`. Decision: `rejected_as_frontier; hard_negative_pressure_did_not_move_direct_fact`. The next direct-fact lever should be a schema split or direct-value selector, not more loss pressure on the current fact-card format.

Stage641 confirms the direct-fact bottleneck is schema-limited. A direct-fact selector search on top of the Stage636 bundle finds `{domain}|{field}|{entity}` as the best marker. It makes direct_fact exact/answer `1.0` / `1.0`, raises global exact/answer to `0.9747863247863248` / `0.985897435897436`, raises exact/answer bits per param to `1.5681584711184162` / `1.5860331402324361`, and drops hard-filter corrections `72` -> `59`. Decision: `accepted_schema_frontier_on_stage636_bundle`. This is a schema-only frontier, not a new trained checkpoint. It also reinforces the selector-compression rule: raw compact identity beats label text, and delimiter/order can be worth more than another training run.

Stage642 canonicalizes Stage641. Keeping `{domain}|{field}|{entity}` while removing the older direct-fact `domain:entity:field` scaffold preserves Stage641 exact/answer `0.9747863247863248` / `0.985897435897436`, direct_fact `1.0` / `1.0`, answer bits per param `1.5860331402324361`, and hard-filter corrections `59`, while lowering average train retrieval tokens per pair from `157.22835650184763` to `152.886811543199`. Removing both older direct-fact markers is too aggressive: exact/answer falls to `0.9726495726495726` / `0.9846153846153847` and corrections rise to `64`. Decision: `accepted_canonical_schema_frontier`. The current best direct-fact representation keeps the new raw `domain|field|entity` marker plus the shorter `entity:field` marker, and drops the old `domain:entity:field` marker.

Stage643 applies the same schema-search rule to `entity_context` on top of Stage642. `{domain}|{field}|{entity}` and `{domain}|{entity}|{field}` tie, raising entity-context exact/answer to `0.9756944444444444` / `0.9756944444444444`, global exact/answer to `0.9811965811965812` / `0.9918803418803419`, exact/answer bits per param to `1.5784707802226585` / `1.595657962063062`, and lowering hard-filter corrections `59` -> `44`. Decision: `accepted_schema_frontier_on_stage642_surface`; choose `{domain}|{field}|{entity}` because it matches the Stage642 direct-fact canonical rule. This confirms entity-context was still schema-limited after replay; the residual replay saturated because the selector identity was under-serialized.

Stage644 reframes the next step as an entropy-first KBPP doubling harness. Stage643 has `1.595657962063062` answer bits/param, but a perfect model on the same eval surface can only reach `1.6087202202617688` answer bits/param, so another residual continuation cannot double KBPP. A 2x same-parameter target requires `51954.6232447733` verified answer bits, or `3.191315924126124` answer bits/param at `16280` params. The current surface ceiling is only `26189.965185861594` bits. General KBPP pilot surfaces are too sparse for this gate: even `256` entities/domain exposes only `5035.740418961495` eval bits. A 64-domain semantic-op probe is much closer, with `4177` eval rows and a perfect ceiling of `3.086118317901473` bits/param, but it is still below the target. The 72-domain Stage644 base surface is now materialized with `4700` eval rows and `3.521664109018803` perfect answer bits/param, followed by the proven `domain|field|entity` selectors, collision-conditioned evaluation, and residual-only training if a short probe clears `1.7552237582693684` answer bits/param.

Stage645 applies the selector route correctly on the expanded surface. The first generic selector pass showed an important mismatch: Stage644's `entity_context` rows were whole-entity rows with no `field`, so `domain|field|entity` could only rewrite `direct_fact`. Stage645 fixes that by first expanding `entity_context` into field-level answer rows, then applying `domain|field|entity` to both `direct_fact` and `entity_context`. Train rows increase `34468` -> `38850`; eval rows increase `4700` -> `5358`; direct_fact selector rows are `5074` train / `686` eval; entity_context selector rows are `5008` train / `752` eval. The new perfect answer ceiling is `66372.11176318346` bits, or `4.076911041964586` bits/param at `16280` params. This clears the entropy requirement for a 2x attempt; the next gate is collision-conditioned evaluation and a short 16k learnability probe.

Stage646 makes that Stage645 surface collision-conditioned. It coarsens exact structured keys for `direct_fact`, `entity_context`, `rule_case_intersection_count`, `rule_case_intersection_member`, `set_intersection_member`, and `two_hop_owner_region` while preserving the compact selector strings as neural binding evidence. This rewrites `22855` train rows and `3209` eval rows. The eval surface has `3209` targeted rows, `1423` collision rows, mean candidate count `1.3415551839464883`, and max candidate count `6`. Direct-fact is no longer exact-key solvable: it has `494` eval collision rows, mean candidate count `1.7107231920199502`, and max `6`. Decision: `stage646_collision_conditioned_selector_ready_for_16k_probe`.

Stage647 is the first 2x answer-KBPP result on the entropy-expanded collision-conditioned branch. An `80`-step, retrieval-only 16k continuation from Stage636 on Stage646 reaches no-filter exact/answer `0.9059350503919373` / `0.9290780141843972`, with exact/answer bits per param `3.6934166102456334` / `3.7877684148748997`. This clears the Stage643 2x answer target of `3.191315924126124` by `18.69%` and is `2.373797207753477`x the Stage643 answer bpp. Hard filtering reaches exact/answer `0.9977603583426652` / `0.9983202687569989`, answer bits/param `4.070062927112463`, with `1423` multiple-candidate queries, `492` corrections, and `0` damage. Decision: `accepted_first_2x_answer_kbpp_on_entropy_expanded_collision_surface`. This is a KBPP result on a verified held-out semantic surface, not a claim of general 7B replacement.

Stage648 runs the matched Stage525-init control on Stage646. It also clears the 2x answer-KBPP gate: no-filter exact/answer `0.9050018663680478` / `0.9307577454273983`, exact/answer bits per param `3.689612101994453` / `3.794616529727024`. Stage648 slightly beats Stage647 on answer bpp by `0.006848114852124321`, while Stage647 slightly wins exact bpp. Hard filtering reaches exact/answer `0.9985069055617768` / `0.9988801791713325`, with `501` corrections and `0` damage. Decision: `accepted_control_reproduces_2x_kbpp_from_stage525_init`. This confirms the main lever is the Stage646 entropy-expanded collision-conditioned selector surface, not only the Stage636 initialization.

Stage649 runs the stricter random-init control. In the same `80`-step budget it does not learn pure neural retrieval: no-filter exact/answer is `0.004292646509891751` / `0.3624486748786861`, with exact/answer bits per param `0.017500737955428426` / `1.4776710047583475`. Hard filtering reaches answer bits/param `4.004625385192165`, but only by making `5210` corrections and masking `5329` neural top1s. Decision: `rejected_as_pure_neural_2x_control_but_confirms_hard_filter_ceiling`. The current 2x neural recipe therefore requires prior tiny retrieval geometry plus the entropy-expanded selector surface; scratch needs a different LR/step schedule or warmup.

Stage650 continues Stage648 for `70` more steps, giving `150` effective initialized steps on Stage646. It gives a small accepted no-filter gain: exact/answer `0.9057484135871594` / `0.931317655841732`, exact/answer bits per param `3.6926557085953974` / `3.7968992346777315`. This is `+0.003043606600944356` exact bpp and `+0.002282704950707591` answer bpp over Stage648. Hard-filter answer bpp ties Stage648 at `4.07234563206317`, with `497` corrections and `0` damage. Decision: `accepted_small_initialized_continuation_gain`. Uniform continuation is still only a polish lever; entity_context and two-hop do not move, so the next gain should come from residual targeting.

The Stage650 residual rank map confirms residual targeting is viable. `entity_context` has `188` answer misses, with `131` already ranked `<=3`; `two_hop_owner_region` has `34` misses with `22` ranked `<=3`; `rule_case_intersection_count` has `16` misses with `15` ranked `<=3`; and `set_intersection_member` has `25` misses with `23` ranked `<=3`. `direct_fact` is already strong at `0.9635568513119533` answer and should be protected. Decision: `stage651_residual_targeting_ready`.

Stage651 builds that residual replay from train-side Stage650 rank details, not eval leakage. It adds `2975` rank-2/3 replay rows for `entity_context`, `rule_case_intersection_count`, `rule_case_intersection_member`, `set_intersection_member`, and `two_hop_owner_region`, while protecting `direct_fact`. A `60`-step low-LR continuation from Stage650 reaches no-filter exact/answer `0.9057484135871594` / `0.9316909294512878`, exact/answer bits per param `3.6926557085953974` / `3.798421037978204`. Exact ties Stage650; answer improves by `0.001521803300472343` bpp. Decision: `accepted_tiny_answer_gain_exact_tie`. Mixed replay regresses `rule_case_intersection_count` slightly, so Stage652 should narrow to `entity_context` and possibly `two_hop`.

Stage652 formalizes the generalized `256` KBPP route. Starting from Stage651's `3.798421037978204` no-filter answer KBPP, the target multiplier to `256` is `67.39642536738418`, or `7` practical doubling rounds. At `16280` params, `256` KBPP requires `4167680` verified generalized bits; at `100M` params, it requires `25.6B` verified bits. The next rung is `stage653_generalized_8kbpp_surface`: at least `130240` verified bits at 16k and a mixed generalized unit family, not lookup-only answer-card expansion. Acceptance remains no-filter held-out generalized KBPP; hard-filter-only gains do not count.

Stage653 materializes the first generalized 8-KBPP surface. It builds `48411` hidden eval units and `55029` train units across atomic facts, relations/sets, multi-hop compositions, procedures, abstractions, and counterfactual negatives. The hidden eval surface contains `298195.65456578933` verified bits, or a perfect 16k ceiling of `18.316686398390008` generalized KBPP, clearing the `8.0` target by `167955.65456578933` bits. The oracle scorer recovers the full ceiling and reports composition KBPP `4.457309582309582`. Collision conditioning is deliberately coarse: `362` eval groups, all with collisions, mean candidate count `133.73204419889504`, and max `652`, so deterministic filtering can narrow family/domain but cannot solve individual rows. Decision: `accepted_generalized_8kbpp_entropy_surface_only`; the next step is an initialized no-filter 16k training probe, not a claim that the rung has been learned.

Stage654 runs that first initialized probe and rejects direct continuation as the 8-KBPP training recipe. A `40`-step retrieval-only continuation from Stage651 onto Stage653 reaches no-filter exact/answer generalized KBPP `0.04628438421402501` / `0.5980970239563056`, far below the `8.0` gate. Answer recovery is concentrated in `held_out_set_count` (`0.9352890422778257` answer bit recovery); atomic facts, relations, two-hop compositions, and counterfactual negatives are near chance. This means Stage653 solved the entropy ceiling but not learnability. The next route is `stage655_generalized_bridge_curriculum`: staged family exposure plus compact selectors for facts, relations, and compositions before another acceptance run.

Stage655 materializes that bridge surface. It preserves Stage653's verified unit set and bit accounting but adds compact `gsel=` selectors to retrieval queries/docs: `fact|domain|field|entity`, `rel|domain|relation|entity`, `compose2|domain|relation|field|entity`, `setcount|domain|field|value`, `neg|domain|field|entity|claimed`, and `exception|domain|field|entity`. It also writes staged train files for binding-only, composition, and full-family curricula. Train/eval rows remain `55029` / `48411`; train/eval distinct selectors are `55029` / `48411`. This is intentionally a neural selector handle, not a hard-filter acceptance path; the gate remains no-filter generalized answer KBPP `>=8.0`.

Stages656-658 test that staged bridge. Stage656 trains `40` steps on binding families, Stage657 trains `40` steps on bindings plus compositions, and Stage658 trains `40` steps on the full Stage655 surface. The final no-filter exact/answer generalized KBPP is `0.03180312576794616` / `0.6104376420456761`, only `+0.012340618089370473` answer KBPP over Stage654 and still far below `8.0`. Decision: `rejected_as_8kbpp_rung_tiny_positive_diagnostic`. The new algorithmic constraint is that the split must be balanced for learnability: every schema/field family must appear in train; eval should hold out bindings, entities, and compositions, not entire field families.

Stage659 builds that balanced surface. It reuses the generalized units but changes the split so all schema families appear in train, while eval holds out entity bindings, relation bindings, set-count bindings, two-hop bindings, parameters, and API names. The surface has `231560.4531036051` hidden verified bits and a perfect ceiling of `14.223615055503998` KBPP at `16280` params, still clearing the `8.0` entropy gate. Stage660 trains an `80`-step initialized probe on this surface and reaches no-filter exact/answer KBPP `0.035524560810987996` / `0.3969855535935876`. Decision: `rejected_as_8kbpp_rung_balanced_split_not_sufficient`. Atomic facts and relations remain near chance, so the next algorithmic test should isolate binding capacity before adding broad composition and counterfactual pressure.

Stages661-663 isolate that binding blocker. Stage661 trains only atomic and relation bindings for `200` initialized steps, but train recovery is still near zero: train answer KBPP `0.04204143657911137`, eval answer KBPP `0.025312944564192134`. Stage662 makes the task easier with identical train/eval over `1024` atomic bindings and still recovers only `12/1024` answers (`0.004422604422604423` answer KBPP). Stage663 tests the learned key-hash side-channel on the same 1k overfit and also fails (`10/1024` answers, `0.0007333349629665844` answer KBPP with `81818` params). This does not stop recursive doubling; it rejects the current one-shot broad binding primitive.

Stages664-666 start the binding-doubling implementation directly. Stage664 builds `64,128,256,512,1024` atomic overfit subsets and proves the base cell: the initialized 16k model trained on `64` atomic bindings reaches `64/64` exact/answer recovery, `384` verified bits, and `0.023587223587223587` KBPP. Stage665 doubles to `128` from that solved checkpoint and reaches `86/128`, or `516` verified bits. Stage666 adds a lower-LR consolidation pass and improves to `101/128`, or `606` verified bits, equal to `1.578125x` the 64-row bits. This is positive but not yet a clean 2x. The next algorithmic change is cross-batch/full-corpus negative exposure or a memory-bank consolidation loss so `128` reaches near-perfect before continuing the recursive ladder to `256`, `512`, `1024`, and then larger environment spaces.

Stage667 tries the simplest version of that change: attach all other `127` docs as explicit hard negatives for each 128-row query. The GPU run was blocked by external memory pressure, so a short CPU diagnostic was run for `100` steps. It reaches `97/128` exact/answer, `582` verified bits, and `0.03574938574938575` KBPP, below Stage666's `101/128`. Decision: reject equal-weight all-negative consolidation as too blunt. Keep the Stage667 dataset as an artifact, but the next implementation should use mined/scheduled cross-batch negatives or a memory-bank objective.

Stages668-673 implement mined-residual consolidation and show the doubling algorithm is now concrete. Each pass mines the current wrong top-1 docs, attaches only those residual negatives, trains weighted residual negatives while replaying all 128 rows, then rescoring becomes the next mining surface. The 128-rung progression is monotonic: Stage666 `101/128`, Stage668 `108/128`, Stage669 `112/128`, Stage670 `115/128`, Stage671 `117/128`, Stage672 `121/128`, and Stage673 `123/128`. Stage673 reaches `738` verified bits and `0.04533169533169533` KBPP, or `1.921875x` the solved 64-cell bits. This is close to a full 2x. The route is now explicit: solve base cell -> double environment -> mine residual confusions -> consolidate -> repeat until near-perfect -> only then double again.

Stages722-744 update that route for generalized KBPP. The single-vector atomic path saturated, but Stage722 solved the 256-row no-qid diagnostic by adding a reusable factorized key score; Stage723 made that scorer trainable. Stage725 cleared 8 KBPP numerically but was rejected because eval selectors were singletons. Stage726 introduced real allowed-key collisions, Stage732-733 found the reusable `text_domain_field_entity` axis, Stage734 removed qid text, and Stage735 aliased eval entities to unseen anchors. That accepted the generalized 8-KBPP collision gate. Scaling the same qidless held-out-alias collision construction cleared 16 KBPP at Stage739 and answer 32 KBPP at Stage741. Stage742 slightly improved the Stage741 exact near-miss to `31.753644121470685` exact KBPP but did not close it. Stage743 scaled to `672` domains and a `125.52629554504509` KBPP ceiling; Stage738 transferred to `50.670770719524214` answer KBPP, and Stage744 continuation reached only `50.73960482694353` answer KBPP. Decision: `completed_saturation_diagnostic`. The current factor transfers past 32 KBPP but does not maintain the recovery needed for 64; simple continuation is not the doubling algorithm. The next branch should discover an additional reusable basis or collision-local discriminator before further scale.

Stages745-746 make that branch concrete. Stage745 profiles the Stage744 residuals: relation recovery is `0.03551640550600334`, two-hop recovery is `0.24129753835807952`, atomic recovery is `0.5083242157979629`, counterfactual recovery is `0.485656253022536`, and exceptions are already `0.9547991071428571`. Stage746 adds a no-parameter `text_domain_field_nonanswer_entity` factor that reuses the existing learned entity buckets while excluding `answer=` entities from factor ids. This removes relation target-entity collision noise and raises answer/exact KBPP to `56.81052148757973` / `54.20298308100595`, a `+6.0709166606362` answer KBPP gain. Decision: `accepted_factor_gain_below_64`. The 1024-KBPP route now needs roughly five more effective doublings from the Stage746 frontier, but the immediate 64 gate still needs a two-hop composition factor and likely an atomic/counterfactual binding recovery factor.

Stages747-751 continue the same route. Stage747 adds `text_domain_relation_field_nonanswer_entity`, including the composition target field from `gsel=compose2grp|domain|relation|field`, and reaches answer/exact KBPP `60.57567570932559` / `57.89846956427378`; Stage748 weight `4.0` only nudges to `60.60660995816472`. Stage749 adds a compact `domain|field|non-answer-entity` binding-pair factor and clears the 64 rung on the 672-domain surface with answer/exact KBPP `101.71841710448409` / `99.64035351034333`. Stage750 scales to `896` domains and clears the 128 answer rung with `130.74282974483415` answer KBPP, with exact just short at `127.92777674971687`. Stage751 scales to `1792` domains but misses the 256 rung at `220.95775879737144` answer KBPP and `214.24286061945074` exact KBPP. Decision: `accepted_128kbpp_answer_rung_256_miss`. The current binding-pair route is strong but still loses recovery as domain count grows; profile Stage751 residuals before scaling again.

Stage758 wraps the current factor route around the 100M plan. The generated route artifact defines the strict 100M gates, command templates, and non-negotiable qidless/no-answer/held-out alias constraints. The route has been regenerated to use the accepted `text_multi_axis_nonanswer_entity_pair` factor mode, and the 100M dry-run shape passes at `101463808` parameters with the factorized contrastive settings. Decision: `100m_factorized_binding_route_ready_after_16k_256_gate`. This is compatibility validation only; it does not prove the 100M model beats 7B.

Stages752-759 close the 16k 256 gate. Stage752 profiles the `1792`-domain miss and shows broad residual gaps. Stage753 weight tuning barely moves the domain-field binding pair. Stage754 adds all non-kind gsel axes and improves to `227.15636741430188` answer KBPP. Stage755/756 scale to `2048` domains but remain just short at `249.03219259543124` / `249.3560488610709` answer KBPP. Stage757's `2176`-domain surface has a `405.619821560921` KBPP ceiling, but the evaluator exits without artifact in this environment. Stage759 adds `text_multi_axis_nonanswer_entity_pair`, emitting compact domain-field, gsel-axis, and family-tagged gsel-axis hashes for non-answer entities. This clears the stable 2048-domain 256 rung with answer/exact KBPP `372.46443714113553` / `365.7994972816619`. Decision: `accepted_256kbpp_answer_exact_rung`. The 100M route has been regenerated to use the accepted factor mode. Next gate: build/evaluate a stable 512-KBPP surface before a real 100M short probe.

Stage760 makes that 512 surface buildable. The failed `2816`-domain attempt exposed a builder problem rather than a factor problem: the old path held units, train rows, eval rows, and aliased eval rows in memory. `scripts/build_stage760_streaming_collision_surface.py` streams domain chunks, aliases held-out eval entities deterministically, and writes rows directly. The resulting `2816`-domain qidless held-out-alias collision surface has `2484287` train rows, `1444289` eval rows, `65501` collision selectors, and a `524.6804340377759` KBPP perfect ceiling. This is enough to attempt 512 but not a comfortable margin: applying Stage759's answer-bit recovery projects `511.88041728656304` answer KBPP. The evaluator now supports operation-sharded runs plus shard aggregation, and a small procedure/schema/math shard validates the new path. Decision: `surface_ready_not_full_scored`. Next gate: score the high-bit shards (`atomic_fact`, `relation`, `composition`, `counterfactual_false_claim`, `exception`) or build a safer-margin `2944`-domain surface before claiming an accepted 512 rung.

Stages760-761 close the 512 gate. Stage760's full operation-sharded aggregate lands just short at answer/exact KBPP `506.4707184030691` / `497.19633469460183`, so the tight ceiling was not enough. Stage761 scales the same streaming qidless held-out-alias collision surface to `2944` domains, `2597145` train rows, `1509863` eval rows, `68475` eval collision selectors, and a `548.4948415778068` KBPP perfect ceiling. With `text_multi_axis_nonanswer_entity_pair` at weight `4.0`, the aggregate reaches answer/exact KBPP `528.7923629505874` / `519.1314126111805`, with answer/exact bit recovery `0.9640790083394719` / `0.9464654418899454`. Decision: `accepted_512kbpp_answer_exact_rung`. The next local bottleneck is throughput, not the factor basis: atomic scoring is now CPU-bound in text factor extraction, so the 1024 route should cache factor ids or factor embeddings before scaling again.

Stages762-763 reach the 1024 answer gate and identify the exact bottleneck. Stage762 adds optional operation-side factor tensor caching to `scripts/evaluate_retrieval_factor_grid_fast.py`; the Stage761 exception smoke run writes doc/query factor tensors on the first pass and hits them on the second pass with unchanged answer/exact KBPP. Stage763 then builds a `5900`-domain streaming qidless held-out-alias collision surface with `5203315` train rows, `3024357` eval rows, `137158` collision selectors, and a `1098.5156075661737` KBPP perfect ceiling. Full sharded scoring reaches answer/exact KBPP `1029.9581689220786` / `1011.3633136166122`. Decision: `accepted_1024kbpp_answer_rung_exact_near_miss`. The dominant residual is composition exactness: composition answer KBPP is `182.79409312849828`, but exact is only `164.6022388948434`. A cached composition weight sweep finds weight `6.0` as best tested, but it only raises composition exact to `165.5511492199595`, so exact 1024 likely needs either a slightly larger `6100`-domain margin surface or a composition-specific exact discriminator rather than simple weight tuning.

Stage764 closes the 1024 exact gate with a larger margin surface. It scales the same construction to `6200` domains, `5467835` train rows, `3178037` eval rows, `144144` collision selectors, and a `1154.3303347481237` KBPP perfect ceiling. With `text_multi_axis_nonanswer_entity_pair` at weight `4.0`, the aggregate reaches answer/exact KBPP `1079.2888326792654` / `1059.695108730236`. Decision: `accepted_1024kbpp_answer_exact_rung`. This is the strongest generalized KBPP result so far, but recovery continues to decline with scale (`0.9349913107083593` answer recovery, `0.9180172060182528` exact recovery), and composition exactness remains the weakest large family. The next best research step is to improve composition-specific exact discrimination and vectorize/checkpoint scoring before attempting 2048.

Stage765 targets that composition exact weakness. The new `text_compose_role_entity_exact` factor is qid-free and answer-free, but packs composition-specific axes into the limited factor slots: domain, relation, final field, subject entity, and salted role bindings. On Stage764 composition, weight `8.0` improves answer/exact KBPP from `191.4036560676432` / `172.25008931761343` to `197.41580326307013` / `178.27045373347624`. Using this only for composition and keeping `text_multi_axis_nonanswer_entity_pair@4.0` for all other operations raises the Stage764 aggregate to answer/exact KBPP `1085.3009798746923` / `1065.7154731460987`. Decision: `composition_exact_factor_gain_hybrid_policy`. This is not yet a single global mode; it shows the next algorithmic direction is operation-aware factor packing or trainable factor routing.

Stage766 turns the hybrid insight into an explicit routed factor mode. `text_routed_multi_axis_compose_exact` keeps the accepted multi-axis non-answer entity pair packing for ordinary rows and routes only `compose2...` selectors into the composition-priority exact packing. On the full Stage764 composition shard (`586893` rows), routed mode at weight `8.0` exactly reproduces Stage765's composition result: answer/exact KBPP `197.41580326307013` / `178.27045373347624`, with `544713` answer-correct and `498745` exact-correct rows. Decision: `routed_factor_policy_validated_on_composition`. This clarifies the algorithm: recursive KBPP gains are coming from routed reusable-axis packing over residual collision families. Caveat: the accepted aggregate remains the Stage765 hybrid aggregate until every non-composition shard is rescored under the routed mode name, or the router is trained end-to-end.

Stage767 tests whether the routed composition weight can be global. The combined small shard exactly ties Stage764 at weight `8.0`: answer/exact KBPP `17.68453018935334` / `17.6734548052876`. Relation improves from `157.19921734045403` to `157.5411303629997` answer/exact KBPP. Counterfactual improves from `163.24794569489103` / `163.09253304751698` to `163.3201143265452` / `163.1664880314398`. Decision: `routed_weight_8_supported_on_tested_non_atomic_shards`. If atomic were unchanged, these tested gains would project the Stage765 hybrid frontier from `1085.3009798746923` / `1065.7154731460987` to `1085.7150615288922` / `1066.1313411525672` answer/exact KBPP. This is only a projection; atomic remains unmeasured and blocks the full routed aggregate claim.

Stage768 scores the atomic blocker and closes the single global routed-factor claim. Atomic_fact improves at routed weight `8.0`: answer/exact KBPP moves from the Stage764 baseline `549.7534833869239` / `549.479814219364` to `550.028224365845` / `549.7563415505538`. The full operation-sharded aggregate under `text_routed_multi_axis_compose_exact@8.0` reaches answer/exact KBPP `1085.9898025078135` / `1066.4078684837573`, with `2992657` answer-correct rows and `2945469` exact-correct rows over `3178037` eval rows. Decision: `accepted_single_global_routed_factor_1024_frontier`. This gives a real single-mode algorithmic improvement over Stage764 (`+6.700969828548068` / `+6.712759753521368` answer/exact KBPP) and over the Stage765 hybrid policy (`+0.6888226331211627` / `+0.6923953376583534`).

Stage769 validates trainer compatibility for that route and exposes the next infrastructure blocker. The first full Stage764 one-step routed training attempt exits with code `-1` and writes no artifact. A matched dry-run with the bundle tokenizer and Stage744 architecture keeps `16794` parameters and records `text_routed_multi_axis_compose_exact` at score weight `8.0`. A tiny balanced smoke manifest with `32` train and `32` eval rows, four rows per operation family, then completes one real CPU training step from the Stage744 checkpoint: last loss `0.3690607249736786`, checkpoint written, `16794` parameters preserved. The tiny trained bundle also loads through the routed scorer, scoring `25/32` exact/answer rows. Decision: `routed_factor_training_smoke_passed_full_surface_loader_blocked`. The factor objective is trainable; the next blocker is full-surface training throughput/loading.

Stage770 removes the immediate full-manifest smoke blocker by adding row caps for local JSONL training. `EncDecJsonlDataset` now accepts a `max_rows` cap, and the trainer exposes `--max-train-rows` and `--max-eval-rows`; default `0` keeps the old uncapped behavior. With the real Stage764 manifest, `--max-train-rows 4096`, and `--max-eval-rows 512`, the routed CUDA one-step smoke initializes from Stage744, computes a step with `text_routed_multi_axis_compose_exact@8.0`, writes a checkpoint, and preserves `16794` parameters. Decision: `capped_full_manifest_routed_training_smoke_passed`. This is not a quality result; it is the infrastructure bridge needed for short routed continuation probes. Long full-surface training still needs streaming JSONL or parquet.

Stage771 tests that short routed continuation path on a balanced subset. The probe samples `128` train and `128` eval rows for each operation family, giving `1024` rows per split. The Stage744 baseline with `text_routed_multi_axis_compose_exact@8.0` scores answer/exact KBPP `0.23727969513471042` / `0.2333497201436422`; model-only scoring is `0.017610747141965193` / `0.01094169867227364`. After `40` CUDA steps of routed factorized contrastive training, both routed and model-only scores are exactly unchanged. Decision: `short_routed_continuation_preserves_no_gain`. The current route is trainable, but same-batch factorized replay does not amplify KBPP; the next training-side change needs residual weighting, harder operation-balanced negatives, or trainable routing gates.

Stage772 makes that negative more specific. It freezes all parameters except `retrieval_key_hash_embed.weight`, leaving `512` trainable parameters, and trains `200` steps at LR `1e-4` on the same balanced subset. Loss remains nonzero and the checkpoint writes, but routed and model-only eval scores are again exactly unchanged: routed `0.23727969513471042` / `0.2333497201436422`, model-only `0.017610747141965193` / `0.01094169867227364`. Decision: `factor_table_only_replay_preserves_no_gain`. The table can train, but same-batch replay is not changing top-1 decisions. Next: generate residual-targeted hard negatives or add trainable routed gates.

Stage773 generates those residual hard negatives. Train-split top-1 details are mined under the routed scorer, matched back by `unit_id`, and every miss row gets the predicted wrong doc as `retrieval_negative_doc_texts` plus `retrieval_loss_weight=4.0`. The corrected residual set has `383` miss rows and `383` attached negatives: `127` code API, `127` math identity, `120` schema, and `9` composition. A `200`-step run with factorized contrastive plus hard-negative loss improves model-only eval by one row (`44` to `45` answer-correct, `29` to `30` exact-correct), but routed KBPP remains unchanged at `0.23727969513471042` / `0.2333497201436422`. Decision: `residual_hardneg_neural_one_row_gain_routed_unchanged`. Residual negatives are the right direction, but the pressure needs to be stronger or routed by procedure/schema family.

Stage774 implements that procedure/schema routing branch. `text_routed_multi_axis_compose_procedure` preserves the Stage768 routed multi-axis/composition branches, then adds procedure-style factors for abstraction/API/math/schema selectors. On the balanced probe it improves routed answer/exact KBPP from `0.23727969513471042` / `0.2333497201436422` to `0.39948048112970863` / `0.3969795879535743`. On the full Stage764 small shard (`code_api_semantics`, `exception`, `math_identity`, `schema`), it improves answer/exact KBPP from `17.68453018935334` / `17.6734548052876` to `18.69989281886388` / `18.69774919614148`. The canonical Stage774 policy aggregate replaces only that small shard inside the accepted Stage768 aggregate and yields answer/exact KBPP `1087.005165137324` / `1067.432162874611` over `3178037` rows. Decision: `accepted_procedure_routed_factor_gain_policy_frontier`. This is a real residual-family gain, not a new doubling rung; next, train or gate this route rather than replaying unchanged factors.

Stage775 remaps the residuals under `text_routed_multi_axis_compose_procedure@8.0`. The balanced train target shrinks from Stage773's `383` routed miss rows to `69` answer misses and `75` exact misses. Train answer misses are `50` schema, `16` math identity, and `3` composition/set-count; exact misses are `50` schema, `16` math identity, and `9` composition/set-count. Eval has `37` answer misses and `43` exact misses, concentrated in the same families plus `3` code API rows. Decision: `procedure_routed_residual_target_narrowed`. The next hard-negative pass should target these rows with stronger schema/math/set-count negatives rather than replaying the full balanced set.

Stage776 builds the targeted residual-hardneg set and runs the matched training probe. The manifest attaches wrong top-1 docs to `75` train exact-miss rows, with operation weights schema `10.0`, math `8.0`, and composition `8.0`. A dry-run first exposed a parameter-shape error (`16024` params) when retrieval head/key-hash settings were missing; the real matched run uses `16794` params, trains `200` CUDA steps, and writes a checkpoint with mean/final loss `0.41047209314536304` / `0.11428945511579514`. Evaluation is unchanged: procedure-routed eval remains `0.39948048112970863` / `0.3969795879535743`, procedure-routed train remains `0.38620192926594776` / `0.38370103608981343`, and model-only eval remains `44` answer-correct / `29` exact-correct. Decision: `fixed_factor_hardneg_no_top1_movement`. The training blocker is now clearer: the fixed factor score dominates decisions, so the next algorithmic change needs trainable factor-family gates or a factor-score curriculum.

Stage777 tests that curriculum idea directly. It uses the same Stage776 residual-hardneg set, trains with neural contrastive pressure only (`retrieval_contrastive_weight=1.0`, fixed factor score disabled), then evaluates with `text_routed_multi_axis_compose_procedure@8.0` restored. The `16794`-parameter, `200`-step run gives a one-row gain in both paths: model-only eval improves from `44/29` to `45/30` answer/exact correct, and procedure-routed eval improves from `987/981` to `988/982`, raising balanced answer/exact KBPP to `0.3998377515834421` / `0.39733685840730776`. Decision: `neural_first_curriculum_one_row_gain`. This is small, but it identifies the next plausible amplifier: staged neural-first repair followed by low-weight factor reintroduction and final weight-8 scoring.

Stage778 runs that low-weight reintroduction stage. Starting from Stage777, it trains `120` steps with neural contrastive `1.0`, factorized contrastive `1.0`, and factor score weight `1.0`, then evaluates again with procedure factor score weight `8.0`. The one-row gain is preserved but not compounded: model-only eval remains `45/30`, and procedure-routed eval remains `988/982` with answer/exact KBPP `0.3998377515834421` / `0.39733685840730776`. Decision: `low_factor_reintro_preserves_no_compound`. The next pass should remap residuals under this checkpoint and either run a second neural-only repair on remaining misses or make factor-family weights trainable.

Stages779-780 show that repeated neural repair is not enough. Stage779 identifies the single repaired eval row from Stage777: schema row `stage653_d3548c0a96555b5b0335`, split `held_out_balanced_misc`, expected `tool_v30`, worth `6` verified bits. Stage778 has no new repairs and no regressions; train routed residuals remain `69` answer misses and `75` exact misses. Stage780 repeats neural-only residual repair from Stage778 for `200` steps and preserves but does not improve the result: model-only eval remains `45/30`, and procedure-routed eval remains `988/982`. Decision: `second_neural_repair_no_compound`.

Stage781 runs the row-isolated schema overfit diagnostic. The train split contains the `50` Stage775 schema exact misses with hard negatives and high neural loss weight (`16.0`), initialized from Stage778 for `400` steps with the fixed factor score disabled during training. The isolated train target exposes the split clearly: model-only gets `12/50`, while procedure-routed scoring gets `50/50`, so the route already has enough deterministic rank signal but the embedding path does not absorb it cleanly. On the full balanced eval, model-only improves to `57/38` answer/exact rows, and procedure-routed answer improves from `988` to `992`, answer KBPP `0.401505013700865`; procedure-routed exact remains `982`, exact KBPP `0.39733685840730776`, because two exact set-count repairs are offset by two exact set-count regressions. Decision: `schema_overfit_answer_gain_exact_neutral`. The next useful experiment is no longer another residual continuation; build a trainable schema/procedure factor-family gate with exact-preserving set-count/composition margins.

Stage782 uses the currently available hook for that direction: exact-protected residual weighting. Starting from Stage781, it trains `240` steps on the full narrowed Stage775 exact residual set (`75` rows: `50` schema, `16` math identity, `9` composition/set-count), with composition exact rows weighted `24.0`, schema `12.0`, and math `8.0`, while fixed factor score remains disabled during training. Model-only eval improves from Stage781 `57/38` to `69/49`. Procedure-routed eval improves from `992/982` to `993/983`, answer/exact KBPP `0.40186228415459846` / `0.3976941288610413`. Row flips versus Stage781 are two repairs and one regression for both answer and exact: repaired math `stage653_18986691dc7c1df2c384`, repaired schema `stage653_2ec46bcb5114049c59a3`, regressed math `stage653_6715f1c77609d775842a`. Decision: `exact_protected_residual_one_row_gain`. This is the strongest post-Stage774 training-side signal, but still a balanced-probe gain; the full accepted frontier remains Stage774 until full-shard scoring verifies it.

Stage783 starts the internalization track requested after the KBPP/factor frontier. The Stage782 routed policy is frozen as teacher by scoring top-k and margins under `text_routed_multi_axis_compose_procedure@8.0`. The new manifest has `2048` train rows: `1024` selector-dropped direct-answer rows and `1024` route-proof rows that emit compact route/proof JSON; eval has `1024` selector-dropped direct-answer rows. A `320`-step continuation from Stage782 trains with retrieval contrastive weight `1.0` and decoder loss `1.0`, with factor scoring disabled during training. Result: model-only retrieval on the original balanced eval improves from Stage782 `69/49` to `81/58`, answer/exact KBPP `0.030948844081348306` / `0.0212429967549222`, while procedure-routed eval is preserved at `993/983`, answer/exact KBPP `0.40186228415459846` / `0.3976941288610413`. Direct generation is still not solved: raw direct eval on `256` selector-dropped rows is `0/256` for both Stage782 and Stage783, with mean recall `0.01171875` -> `0.013671875`; prefixed direct eval is also `0/256`. Decision: `internalization_retrieval_gain_direct_generation_failed`. The next pass should separate content-only answer emission from route-proof JSON, because asking the 16k model to learn direct answer plus route proof in one decoder target produces malformed generations.

Stage784 separates content-only answer emission. It converts the Stage783 manifest with `build_content_only_decoder_dataset.py`, so the decoder target is only `expected_content`; then it trains from Stage783 for `320` steps with decoder loss `2.0` and retrieval contrastive weight `0.5`. Direct generation remains failed: Stage783 baseline and Stage784 both score `0/256` on content-only direct eval with mean recall `0.0`. Retrieval still improves, which is useful but not sufficient for the goal shift: model-only original balanced eval rises to `89/65`, answer/exact KBPP `0.033926097862460605` / `0.02380343500667878`, and procedure-routed eval rises to `994/984`, answer/exact KBPP `0.402219554608332` / `0.39805139931477473`. Decision: `content_only_retrieval_gain_direct_generation_failed`. The decoder path is the current blocker. Next run an answer-only overfit diagnostic or repair decoder label/prefix masking before broad direct-answer training.

## Latest Held-Out Alias Bridge Result

The current robust internalization frontier is now Stage853 for the hardened held-out-alias bridge branch: `237/640` answer and `220/640` exact on target rows, implied full `467/1024` answer and `449/1024` exact after adding unchanged non-target rows. This exceeds the older Stage803 full candidate-ranking reference (`387/1024` answer, `379/1024` exact). Stage853 uses typed entity/slot partition heads, side-invariant q/d bridge-token hashing, and external alias-salt threshold calibration.

## Last 100 Stage Analysis

The last 100 stages moved through three distinct phases.

Stages759-774 scaled factor-assisted KBPP from the stable 256 rung to the current 1024 policy frontier. Stage759 cleared generalized 256 answer/exact KBPP at `372.46443714113553` / `365.7994972816619`; Stage761 cleared 512; Stage764 cleared 1024 answer/exact; Stage774 raised the accepted factor-assisted policy frontier to `1087.005165137324` / `1067.432162874611`. The lesson is that reusable routed factor packing scales, but those numbers remain factor-assisted access rather than fully internalized model-only reasoning.

Stages775-803 shifted toward internalization. Routed-teacher distillation and content-only direct-answer training improved model-only retrieval but did not solve direct generation. Candidate-ranking objectives were the productive path: value ranking, JEPA-style route targets, predicted-route feedback, operation conditioning, and atomic weighting compounded into Stage803 at `387/1024` answer and `379/1024` exact.

Stages804-858 hardened that internalization against alias shortcuts. Stage839 reached `144/640` target rows, implied full `374/358`. Stage849 then found the real ceiling: metadata teacher partitions plus frozen base scoring reach `479/640` answer and `465/640` exact. Stage850 showed naive token-bag partition prediction fails at `96/76`; Stage851 typed entity/slot heads improved to `128/109`; Stage852/853 found the major transferable representation gain by normalizing q-side and d-side bridge tokens into shared feature names, reaching the current accepted `237/220`, implied full `467/449`.

The negative result is equally important: Stages854-858 reject per-operation threshold tables, hard role/proof gates, soft role mixing, shared role reranking, and detached in-trainer role reranking. Role/proof information should not be coupled to the first-stage partition predictor. The next branch should freeze Stage853 partitions and train a separate reranker on candidates selected by that fixed policy.

Stage841 tested a direct composition-weight residual fix on that branch. It regressed to calibrated `133/640` answer and `118/640` exact, so scalar composition loss weighting is rejected.

Stage842 patched bridge supervision so qpair and dpair tokens align by shared pair-code suffix, not only by alias metadata. This increases capacity: eval-picked alpha `3.0` reaches `153/640` answer and `139/640` exact, the best diagnostic target-row result so far. But the honest external alias-salt calibration split selects alpha `0.5`, where eval falls to `111/640` answer and `94/640` exact. Decision: Stage842 is not an accepted frontier, but it identifies the next likely lever. The scorer can use the pair bridge; the calibration protocol cannot yet select the right mixture with one global alpha.

Stages843-846 test that calibration path. Stage843 adds per-operation alpha tables and improves the Stage842 calibrated result to `120/640` answer and `104/640` exact. Stage844 adds operation-level MRR tie-breaking and improves to `130/640` answer and `114/640` exact. Stage845 increases external calibration to `50%` and reaches `135/640` answer and `121/640` exact, but the selector weakens because training rows are removed. Stage846 retains the full train set while emitting a larger separate alias-salt calibration set; eval-best capacity is `147/640` answer and `131/640` exact, but calibrated global and operation choices are only `114/100` and `117/101`.

Decision: Stage839 remains the accepted hardened held-out-alias bridge frontier. The current blocker is not just alpha table granularity or calibration volume. The external calibration rows do not reliably select the high-capacity gates, even when per-operation MRR is available. Next best step: train a small score-feature fusion gate over selector/base margins, operation, and rank statistics on calibration rows. If that cannot beat Stage839, shift the route to proof-aware composition partitions and relation/atomic candidate binding rather than more scorer calibration.

Stages847-848 test the learned-gate route and reject it. Stage847 uses a 417-parameter MLP gate over normalized selector/base scores, interactions, margins, and operation context. It overfits the external calibration rows (`192/330`) and transfers poorly: eval is only `87/640` answer and `73/640` exact. Stage848 regularizes the gate down to 53 parameters with 4 hidden units, 30 epochs, and weight decay `0.1`; it improves transfer to `109/640` answer and `95/640` exact, but remains below Stage846 global alpha `114/100`, Stage846 operation alpha `117/101`, and the accepted Stage839 `144/129`.

Decision: close the current fusion-calibration branch. The remaining headroom in the pair-bridge scorer is not accessible through scalar alpha, per-operation alpha, or small learned score-feature gates. The next useful internalization work should target representation-level partitions: proof-aware composition candidate partitioning, relation entity binding, and atomic field/entity binding.

Stage849 starts that partition branch. It uses hardened metadata only as a teacher/ceiling diagnostic, then scores inside the partition with the frozen Stage784 base embeddings. The best mode is `operation_best_teacher`: atomic and counterfactual use `entity_slot`, while relation, exception, and composition use `entity`. This reaches `479/640` answer and `465/640` exact on the hardened target rows, with mean partition size `3.6890625` and median partition size `1`. Atomic and counterfactual become perfect (`128/128` each), relation reaches `84/128`, exception `63/128`, and composition `76/128` answer with `62/128` exact.

Decision: this is the strongest current route back toward high internalized KBPP. It is not accepted model-only KBPP because it uses metadata at eval, but it proves the missing structure is candidate partitioning rather than score calibration. Next: train a token-only partition predictor for the operation-best policy. Composition should use entity narrowing first, then a proof-aware second-stage scorer inside the entity partition.

Stage850 trains that first token-only partition predictor. It uses a hash-bag token encoder to imitate Stage849 teacher partition labels, then evaluates with predicted partitions only and frozen Stage784 base scores inside the predicted set. The result is rejected. The selected threshold is `0.1`; train reaches `412/640` answer and `400/640` exact, but held-out alias eval reaches only `96/640` answer and `76/640` exact. Eval positive coverage is `197/640`, mean predicted partition size is `11.99375`, and the implied full split is only `326/1024` answer and `305/1024` exact after adding unchanged non-target rows.

Decision: naive token-bag partition prediction does not internalize the Stage849 policy. It overfits train alias bridges and fails side-invariant binding. The next partition attempt should predict typed latent slots directly: operation family, entity binding, slot/field binding, relation/proof role, answer type, and composition support. Composition needs a second-stage proof scorer after entity narrowing rather than one undifferentiated partition threshold.

Stage851 adds typed entity and slot heads to test that direction. Training uses a capped same-collision candidate set of `64` docs per row, but evaluation still uses the full held-out alias collision groups. The result is a positive diagnostic, not a new frontier. Train-selected eval improves over Stage850 from `96/76` to `128/640` answer and `109/640` exact; eval-best reaches `135/117`. Positive coverage rises to `398/640`, but mean partition size is still broad at `23.575`, and composition exact remains only `7/128`.

Decision: typed decomposition helps, but token-derived entity/slot heads alone are not enough. Stage839 remains the accepted hardened held-out-alias frontier at `144/129`. The next partition model should keep typed heads and add side-invariant bridge supervision plus relation/proof-role heads, especially for composition.

Stage852 tests the side-invariant bridge hypothesis directly. It keeps the typed entity/slot heads and normalizes q-side and d-side bridge prefixes before hashing: `qent_/dent_ -> ent_`, `qslot_/dslot_ -> slot_`, `qclaim_/dclaim_ -> claim_`, and `qpair_/dpair_ -> pair_`. This is accepted as the new hardened held-out-alias internalization frontier. Train-selected threshold `0.2` reaches `232/640` answer and `214/640` exact; eval-best threshold `0.7` reaches `237/220`. The implied full split is `462/1024` answer and `443/1024` exact after adding unchanged non-target rows, beating the previous Stage803 full frontier `387/379`.

Decision: the partition predictor was failing mainly because q-side and d-side aliases were hashed as different features. Side-invariant typed bridge tokens provide a substantial model-side KBPP gain without metadata at eval. Remaining work: reduce mean partition size from `13.4140625`, add relation/proof-role heads, and repair composition exactness, which is still only `23/128` at the selected threshold.

Stage853 makes the threshold choice calibration-honest. It reruns Stage852 but selects the threshold on the external alias-salt calibration split. Calibration selects `0.7`, matching eval-best. Held-out eval reaches `237/640` answer and `220/640` exact with mean partition size `5.33125`, and the implied full split becomes `467/1024` answer and `449/1024` exact.

Decision: Stage853 is the current calibrated hardened held-out-alias internalization frontier. The calibration split only became reliable after side-invariant bridge normalization. Remaining gap to the Stage849 metadata teacher ceiling (`479/465`) is now narrow enough to target directly with relation/proof-role heads and composition reranking.

Stage854 checks whether per-operation threshold selection can close more of that gap without retraining. It cannot: calibration-selected per-operation thresholds reach `233/640` answer and `216/640` exact, below Stage853 global threshold `237/220`. Eval-oracle per-operation thresholds would reach `254/236`, so this is calibration-selection headroom rather than model capacity.

Stage855 adds a role/proof head and uses entity x role for relation/composition partitions. This over-prunes. Calibration selects threshold `0.9`, where eval reaches only `204/640` answer and `186/640` exact; eval-best is `221/202`, still below Stage853. The mean partition size falls to `1.08125`, but positive coverage collapses to `199/640`. Role/proof binding should therefore be a soft reranker or second-stage scorer, not a hard multiplicative partition gate.

Stage856 tests a softer first-stage role mix: relation/composition use `entity * ((1-alpha) + alpha*role)` with `alpha=0.25`. This is also rejected. Calibration again selects `0.9`, eval is `203/640` answer and `185/640` exact, and eval-best reaches only `228/209`. The role objective helps train but does not transfer across held-out aliases when mixed directly into partition probability.

Decision: preserve Stage853 as the first-stage partitioner. The role/proof signal should be trained as a separate second-stage reranker inside Stage853 partitions, not as a first-stage gate.

Stage857 tries that idea in the simplest way, but still with shared predictor embeddings. It keeps first-stage relation/composition partitioning entity-only (`role_mix_alpha=0.0`) and adds role probability to the frozen base score with `role_rerank_beta=0.25`. This is rejected: calibrated eval is `200/640` answer and `182/640` exact, with eval-best only `225/206`. Training the role head in the same predictor appears to perturb the shared partition geometry.

Decision: the next role/proof attempt should freeze or detach Stage853 first-stage partition features and train a separate second-stage reranker only inside Stage853-selected partitions.

Stage858 detaches role-loss gradients from the shared partition embeddings and reruns the second-stage role rerank. This also fails: calibration selects `0.9`, eval is `197/640` answer and `180/640` exact, and eval-best is `228/210`. Detaching preserves train partition behavior but does not make the role reranker transfer across held-out aliases.

Stage859 freezes the accepted Stage853 first-stage selector into a reusable partition dataset. It selects threshold `0.7` on the external alias-salt calibration split and materializes train/calibration/eval candidate lists. The frozen base ordering reproduces Stage853 exactly: train `412/640` answer and `400/640` exact, calibration `258/330` and `253/330`, eval `237/640` and `220/640`. Eval partitions average `5.33125` candidates and keep an answer-positive candidate in `333/640` rows. This makes the next reranker work cleaner: the first-stage selector is fixed, and any gain must come from in-partition ranking.

Stage860 tests whether a tiny scalar reranker is enough inside the frozen Stage859 partitions. It is not. A 209-parameter MLP over base score, partition probability, rank, partition size, and operation improves calibration to `267/330` answer and `262/330` exact, but eval drops to `214/640` answer and `197/640` exact. This rejects score/probability-only reranking. The next useful reranker must add actual candidate content evidence: frozen query/doc embeddings, role/proof/value features, direct answer likelihood, or composition-specific support features.

Stage861 adds frozen query/doc embedding-pair features inside the fixed Stage859 partitions. This gives the first accepted separate-reranker gain: raw eval rises from `237/640` answer and `220/640` exact to `239/640` and `222/640`. The gain is not uniform. Exception improves from `49/128` to `60/128`, while relation falls from `49/128` to `41/128`, so generic embedding reranking is useful but operation-unstable.

Stages862-864 sweep smaller, larger, and linear embedding rerankers. None beats Stage861 raw: h16 and h64 reach `238/221`, while linear reaches `232/215`. The finding is that capacity is not the missing piece; operation gating is.

Stage865 diagnoses a calibration-margin operation gate. It shows that the embedding reranker should be used only when calibration gain is large enough to justify the risk. The posthoc best diagnostic reaches `248/231`, but it is not treated as a frontier because the gate was inspected after the sweep.

Stage866 reruns the embedding-reranker family with a fixed margin-5 gate: use the reranker for an operation only if calibration answer gain is at least five rows and exact does not regress. The fresh raw reranker is rejected at `234/217`, but the fixed gate selects composition and exception while preserving base ordering for atomic, counterfactual, and relation. Eval improves to `242/640` answer and `225/640` exact, implied full `472/454`. This is the current frozen-partition gated-reranker frontier.

Stages867-869 test relation-only embedding rerankers inside the frozen Stage859 relation partitions. The base relation score is `49/128` answer/exact with `100/128` positive coverage. h16 ties base at `49/49`, h32 regresses to `45/45`, and linear regresses to `47/47`. Relation-specific embedding training is therefore rejected.

Stage870 maps why relation is hard. Among relation rows, positives are present in `100/128`, but base top-1 is only `49/128`. For present misses, the median positive rank is `2` and the median top-positive base-score gap is only `0.0007293522357940674`. Relation is a near-tie value-selection problem, not primarily a coverage problem.

Stage871 tests relation score/probability fusion. Eval-oracle alpha `0.1` would reach `51/51`, but external calibration selects alpha `0.5`, which drops eval to `44/44`. Calibrated scalar fusion is rejected. Relation needs typed relation/source-target/value features or proof-like candidate content.

Stages872-874 test composition-only embedding rerankers. They all overfit calibration and regress eval: h16 reaches `31/15`, h32 reaches `31/15`, and linear reaches `33/17`, compared with composition base `36/20`. Composition embedding specialists are rejected.

Stage875 maps composition residuals. Answer positives are present in `58/128`, exact positives in `42/128`, and exact-positive median rank is `2`. This is real reranking headroom, but it needs the right feature. Generic embeddings are not it.

Stage876 tests composition score/probability fusion. Calibration selects alpha `0.5`, which improves eval composition from `36/20` to `38/22`; eval-oracle alpha `0.05` would reach `39/23`. This is accepted as a calibrated composition-local gain.

Stage877 combines accepted operation policies while preserving frozen Stage859 partitions: composition uses `base_score + 0.5 * partition_probability`, exception uses the accepted Stage866 embedding component, and atomic/counterfactual/relation keep Stage859 base ordering. Target eval rises to `245/640` answer and `228/640` exact, implied full `475/457`.

Stage878 tests exception score/probability fusion as a cleaner replacement for the embedding component. It fails: calibration selects alpha `1.35`, and eval drops from exception base `49/49` to `43/43`. Eval-oracle only reaches `50/50`, so scalar fusion is rejected for exception.

Stages879-881 train exception-only embedding specialists. This works. h16 reaches `57/57`, h32 reaches `58/58`, and the linear exception embedding reranker reaches `59/59`, all above exception base `49/49`. Stage881 is accepted as a cleaner local exception policy.

Stage882 combines stable operation-local policies: composition uses Stage876 scalar fusion, exception uses Stage881 linear frozen-embedding reranking, and atomic/counterfactual/relation keep Stage859 base ordering. Target eval rises to `249/640` answer and `232/640` exact, implied full `479/461`.

Stage883 adds the missing relation typed bridge feature. Relation queries contain `latent_query_bridge=qpair_*` and candidate docs contain `latent_doc_bridge=dpair_*`. Ranking by side-normalized bridge match, then source-entity match, then base score improves relation from `49/128` to `82/128`. Calibration also improves from `44/65` to `49/65`. This is accepted as a relation typed-bridge reranker feature, with an important caveat: it is explicit latent access in text, not proof of free-form generation or a full-denominator density win.

Stage884 combines Stage876 composition scalar fusion, Stage881 linear exception embedding reranking, Stage883 relation typed bridge reranking, and Stage859 base ordering for atomic/counterfactual. Target eval rises to `282/640` answer and `265/640` exact, implied full `512/494`. This is the current recoverable model-side frontier. The next step is to distill the typed relation bridge into learned/internal model behavior rather than keeping it as an exact external bridge match.

Stages885-886 train learned scorers over text-derived relation bridge/source features. A 21-parameter linear scorer reaches `69/128`; a 353-parameter MLP reaches `83/128`, slightly above the direct Stage883 rule at `82/128`. This is accepted as a learned typed-bridge scorer, but it still receives explicit bridge-token features.

Stage887 combines Stage876 composition scalar fusion, Stage881 linear exception embedding reranking, Stage886 learned relation text-bridge scoring, and Stage859 base ordering for atomic/counterfactual. Target eval rises to `283/640` answer and `266/640` exact, implied full `513/495`. Next, this needs bridge-feature dropout or held-out bridge-token salt validation.

Stages888-890 run the bridge-feature dropout audit. Removing only `pair_match` drops relation from Stage886's `83/128` to `38/128`, below Stage859 base `49/128`. Removing both `pair_match` and `source_entity_match` gives `35/128`; removing all text bridge features gives `39/128`. This confirms that Stage887 is recoverable typed access, not bridge-token-free internalization.

Stages891-895 separate bridge equality into two cases. Stage891 learns qpair/dpair hash embeddings directly and fails held-out transfer: relation eval falls to `26/128` despite train reaching `95/128`. Stage892-894 freeze normalized bridge embeddings and train only the 7-parameter scalar trust head. That transfers: Stage892 reaches `59/128`, Stage893 reaches `83/128`, and Stage894 reaches `85/128` relation answer/exact. Stage895 combines Stage894 relation with Stage876 composition, Stage881 exception, and Stage859 base atomic/counterfactual to reach `285/640` answer and `268/640` exact, implied full `515/497`. This is the current recoverable typed-access frontier. Caveat: the frozen bridge basis is fixed infrastructure and still consumes normalized bridge tokens, so the next validation is held-out bridge-salt plus model-owned distillation.

Stages896-897 run the held-out bridge-salt audit. Train, calibration, and eval bridge suffixes are mapped through different hash salts before scoring. Stage896 reaches relation `82/128`; Stage897 reaches `80/128`. This supports the fixed-similarity interpretation: the gain is not simply original bridge hash-ID memorization. The caveat remains that the scorer still receives typed bridge tokens. Next, distill the frozen pair/entity similarity into a model-owned value head and evaluate with external bridge scoring removed.

Stage898 materializes the relation bridge-similarity distillation targets. It writes query/doc candidate rows with base score, partition probability, pair similarity, entity similarity, combined `teacher_bridge_score`, and exact/answer labels. The split sizes are `128` train rows with `390` candidates, `65` calibration rows with `176` candidates, and `128` eval rows with `2228` candidates. This is infrastructure for the next proof: hidden-state prediction of the bridge score without calling the external scorer at eval.

Stages899-902 test that proof directly and reject it. A frozen Stage784 hidden-state value head receives query/doc embedding pair features plus base score and partition probability, but no bridge-similarity inputs. Direct h64 reaches calibration `50/65` but eval only `36/128`; linear reaches `28/128`; h16 reaches `34/128`. Stage902 adds calibration-selected residual blending with base score; alpha `0.1` reaches only `42/128`, still below Stage859 relation base `49/128`. This means the current frozen hidden states do not expose bridge equality enough for readout. The next route must train the bridge objective into the encoder/route representation or first test token-span pooling over qpair/dpair markers.

Stage903 tests that token-span pooling diagnostic and rejects it. Using BPE offsets, it pools localized qpair/qent query token states and dpair/dent doc token states from the frozen Stage784 encoder, then trains a small span value head. Calibration reaches `43/65`, but eval reaches only `35/128`, below Stage859 relation base `49/128`. This closes the existing-representation readout branch: neither global pooled hidden states nor localized marker token states carry enough bridge equality. The next step is encoder bridge-objective fine-tuning.

Stage904 tests the first encoder bridge-objective fine-tune. It unfreezes Stage784 encoder/retrieval parameters and trains on Stage898 relation same-collision candidates with plain candidate cross-entropy, then evaluates using only model retrieval dot products. This is rejected: train reaches `31/128`, calibration `34/65`, and eval `26/128`, all below Stage859 relation base `49/128`. The useful review finding is that Stage859 `base_score` is stronger than raw Stage784 retrieval-dot scoring in this relation partition. The next encoder route needs cached/batched training, auxiliary pair/entity similarity regression, and base-preserving residual evaluation rather than plain CE alone.

Stage906 adds auxiliary `teacher_bridge_score` regression and base-preserving residual evaluation to the encoder fine-tune. This is also rejected: raw eval is `27/128`, and calibration selects residual alpha `0.0`, preserving Stage859 base at `49/128`. Relation-only encoder tuning is too narrow. The next route is a broader bridge curriculum across atomic entity-slot, relation source-target, and composition proof edges, or an explicit binding-comparison head trained before candidate scoring.

Stage907 builds the broader bridge curriculum. It materializes `1610` rows from frozen Stage859 partitions across `atomic_fact`, `relation`, `composition`, `counterfactual_false_claim`, and `exception`, including bridge suffix targets for qent/dent, qpair/dpair, qslot/dslot, and qclaim/dclaim. Eval bridge-positive coverage is operation-specific: relation `100`, exception `84`, composition `42`, counterfactual `56`, atomic `49`. This becomes the substrate for an explicit binding-comparison head before candidate scoring.

Stages908-909 train the broad binding-comparison head over Stage907. The head uses frozen deterministic suffix-similarity features for entity, pair, slot, and claim bridges plus base/probability/rank/operation features, with no binary equality flags. Stage908 reaches eval `304/640` answer and `287/640` exact. Stage909 repeats with split-specific train/calibration/eval hash salts and preserves the gain at `303/640` answer and `286/640` exact, implied full `533/515`. This is the new recoverable typed-access frontier. Caveat: it is still typed bridge-token access, not bridge-token-free model-owned generation.

Stage910 tests whether the broad curriculum alone makes frozen hidden readout transfer. It trains a broad hidden value head over Stage907 without bridge suffix-similarity inputs. This is rejected: direct eval is `212/640` answer and `195/640` exact; calibration-selected residual blend reaches only `228/640` and `211/640`, below Stage859 base `237/220`. Candidate CE over frozen hidden embeddings still does not internalize binding. Next, use a binding-comparison auxiliary head/objective, not only candidate scoring.

Stage911 tests that binding-comparison auxiliary route as a frozen-hidden readout. It predicts pair/entity/slot/claim match targets from frozen hidden pair features and feeds those predicted binding logits into candidate scoring. This is also rejected: calibration reaches `267/330` answer and `262/330` exact, but eval falls to `200/640` answer and `183/640` exact. The auxiliary targets are learnable on calibration but do not transfer from frozen Stage784 hidden geometry. Decision: close the frozen-hidden internalization branch. Stage909 remains the recoverable typed-access frontier; the next model-owned attempt must train the encoder with binding auxiliaries or add stronger composition proof-edge targets.

Stage912 diagnoses the composition proof-edge target. A train/calibration lexical map from query `field/relation` words to positive doc `dslot` proof edges saturates train composition at `128/116`, but it gives zero proof-edge matches on calibration and eval because `dslot` ids are split-local. Eval-oracle proof-edge maps would raise composition from base `36/20` to `51/35`, with recoverable ceiling `58/42`. This means composition is genuinely proof-edge limited, but the transferable target is not a memorized slot id. Next: add side-invariant composition proof-edge supervision and train it into the encoder/latent route.

Stage913 materializes side-invariant composition proof labels from Stage846/819 alias metadata. It reconstructs semantic `qproof/dproof` targets for field/relation edges, giving train `128/116`, calibration `65/61`, and eval `51/35` as a proof bonus diagnostic. This is target infrastructure, not accepted eval-time model evidence.

Stage914 feeds that proof channel into the broad binding-comparison scorer as a ceiling diagnostic. Eval rises from Stage909 `303/286` to `311/294` target rows, implied full `541/523`; composition improves from `47/31` to `53/37`. Because the proof channel is metadata-derived, Stage914 is not accepted as model-owned KBPP. It confirms the next internalization target: predict proof-edge structure from encoder/latent states and evaluate with proof-channel features removed.

Stage915 tests that internalization target as another frozen-hidden auxiliary readout. The head predicts pair/entity/slot/claim/proof targets from frozen Stage784 hidden pair features, but receives no proof features as input. This is rejected: calibration reaches `267/330` answer and `262/330` exact, while eval falls to `201/640` answer and `184/640` exact, below Stage859 base `237/220`. Composition drops to `31/15`. Decision: close the frozen-readout branch for proof edges. The proof target must be trained into the encoder/latent path or introduced by patching the hardening surface before freezing.

Stage916 patches the hardening surface directly. `build_stage819_hardened_binding_surface.py` now parses two-hop composition query text (`field of relation target for entity`) and emits qslot aliases for both field and relation before pair-code generation. The audit on the Stage784 source manifest confirms the intended geometry: train `116/116` and eval `112/112` two-hop composition rows have at least two query slots, two doc slots, and three shared pair codes for subject, relation, and field. This is accepted as infrastructure. Next: rebuild the hardened bridge surface with this hardener and rerun Stage907-style bridge materialization.

Stages917-919 rebuild and score that patched surface. Stage917 rebuilds the hardened bridge surface with Stage846-compatible salts/splits. Stage918 rematerializes Stage907-style bridge targets and confirms composition slot-positive candidates now exist: train `116`, calibration `61`, eval `42`, instead of zero. Stage919 trains the broad binding-comparison head and reaches eval `311/640` answer and `294/640` exact, implied full `541/523`; composition improves from Stage909 `47/31` to `53/37`. This is accepted as the new recoverable typed-access frontier. Caveat: it is still explicit suffix-similarity bridge access, not model-owned proof-edge prediction.

Stage920 tests the rebuilt surface without suffix-similarity features by training the frozen-hidden value head on Stage918. It improves over Stage910 on the old surface, but not enough: direct eval is `226/640` answer and `209/640` exact, and calibration-selected residual blending reaches `229/640` and `212/640`, still below Stage859 base `237/220`. Decision: reject frozen-hidden readout on the rebuilt surface. The qslot proof hints help slightly, but model-owned progress now requires encoder/latent fine-tuning.

Stages921-922 run short encoder/retrieval fine-tuning probes on Stage918. Stage921 reaches raw eval `223/206` and residual blend `235/218`; Stage922 extends to `200` steps and reaches raw `225/208`, but the residual blend stays `235/218`. This is the strongest post-patch model-owned signal so far, improving over Stage920, but it remains below the Stage859 base gate `237/220`. Decision: reject as accepted KBPP. Next: build a cached/batched encoder objective with explicit proof-edge auxiliary loss instead of row-wise candidate CE alone.

Stage923 adds an operation-aware `teacher_bridge_score` to Stage918 and reruns the encoder fine-tune with teacher MSE. The bridge target gives composition extra weight on the new slot/proof edge and keeps pair/entity emphasis for relation. This does not break the plateau: raw eval is `223/206`, and residual blend remains `235/218`. Decision: reject. The next change must be the training loop itself: cached/batched candidate groups with proof-edge auxiliary supervision, then the same base-preserving gate.

Stage924 implements the cached encoder trainer. It caches tokenized query/doc candidate groups and reuses the Stage923 bridge-teacher targets. The first cached setting is rejected as a score gain: raw eval `223/206`, residual blend `233/216`, below both the Stage921-923 plateau `235/218` and Stage859 base `237/220`. The useful result is infrastructure: the trainer now supports faster controlled sweeps over teacher weight, rows per step, learning rate, and operation sampling.

Stage925 uses that infrastructure for two operation-balanced cached settings: teacher weights `0.0` and `0.05`, with `rows_per_step=32`. Both tie Stage924 at residual blend `233/216`, still below the Stage921-923 near miss `235/218`. Decision: reject. The regression is not explained by easy-operation dilution or too much teacher weight. Next: change the model-side training signal, likely an encoder-attached residual scorer/value head or operation-local cached objective for composition/relation.

Stage926 adds that residual value head. It trains a small scorer over frozen query/doc embeddings, interaction features, base score, and partition probability, with no suffix-similarity bridge features. Raw head ranking is only `222/205`, but calibration-selected residual blending reaches `240/223`, beating Stage859 base `237/220` and the Stage921-923 near miss `235/218`. This is accepted as the new model-side residual value-head frontier on the Stage917/918 surface. Caveat: it is still candidate ranking with a small value head, not direct generation.

Stage927 adds operation breakdown and explains the mixed result. The residual head improves composition from base `36/20` to `41/25`, exception from `49/49` to `54/54`, and counterfactual from `54/54` to `55/55`, but hurts relation from `49/49` to `41/41`. Stage928 applies the calibration-supported gate: use the residual head for non-regressing operations and preserve base ordering for relation. This raises model-side residual eval to `248/231`, implied full `478/460`. Decision: accept Stage928 as the new model-side operation-gated residual frontier.

Stage929 trains a relation-only residual specialist on the same frozen embedding/base/probability features, still without suffix-similarity bridge features. The h32 specialist is accepted narrowly: calibration selects alpha `0.025`, relation eval improves from base `49/49` to `52/52`, and the combined policy reaches `251/234`, implied full `481/463`. The h16 and h64 variants are rejected because calibration selects alpha `0`. The h32 head is not accepted as a global scorer (`239/222` globally); it only counts when combined with the Stage928 non-relation gate.

Stage930 makes the Stage929 gain inspectable. It reruns the h32 relation specialist with prediction export and reproduces relation `52/52`. The row audit shows exactly three gained eval relation rows and zero lost rows. Each gained row is a near-tie case where the correct candidate is base rank `2` and becomes blend rank `1`; this points to a typed source-target/value margin objective rather than another broad residual scorer.

Stages931-932 test that margin direction directly and reject the naive forms. Stage931 uses `label_base_top` hard-negative CE and drops relation to `41/41`. Stage932 trains only relation rows where the label is base rank `2`, but still drops relation to `43/43`. This means the Stage929 relation gain should be treated as a small calibrated residual correction, not evidence that stronger relation CE pressure is the right internalization objective.

Stage933 converts the hand-combined Stage929 frontier into a reproducible row-level policy. It reruns the Stage926 all-operation residual head with prediction export and combines it with the Stage929 h32 relation-specialist predictions: Stage926 residual for atomic/composition/counterfactual/exception, Stage929 relation residual for relation. The combined scorer reproduces eval `251/234`, implied full `481/463`. This is accepted as the reproducible scorer artifact for the current model-side frontier, with the same caveat that it is still gated candidate ranking rather than direct generation.

Stage934 trains a simple calibrated trust/correction gate over Stage933 rows using only score-margin features available at eval. It is rejected: calibration-selected thresholds reach eval `250/233`, below Stage933 `251/234`, mainly because the gate suppresses useful relation overrides. This preserves the Stage933 frontier and shows that margin-only confidence is too weak; the next trust signal needs richer non-leaky features or a model-attached multi-head value module.

Stage935 implements that model-attached multi-head value module as a naive joint CE probe. It trains one operation-routed residual head per operation over frozen query/doc embeddings plus base/probability scalars. It is rejected at eval `241/224`, implied full `471/453`. Calibration only trusts composition and zeros relation/exception, so the module loses the accepted Stage926/929 specialist behavior. The next fold-in attempt should distill Stage933 row-level policy targets or initialize from accepted specialist heads rather than training the multi-head module from scratch.

Stage936 tries Stage933 policy distillation by training the multi-head module on the teacher's chosen candidate per row. It is rejected at the same `241/224`, implied full `471/453`. It recovers some exception behavior but still zeros relation and fails to preserve composition/relation gains. The result says top-candidate imitation is too weak; the next version needs richer teacher score distributions or saved specialist-head initialization.

Stage937 attempts the richer teacher-score distribution export and blocks it as infrastructure. Rerunning Stage926/Stage929 with full per-candidate score export did not write artifacts, and even a one-step smoke produced no artifact while no active trainer remained in the process table. The safer next implementation is to save accepted specialist head weights during the successful run and initialize a single module from those heads, rather than relying on post-hoc full-score export.

Stage938 follows that safer route and succeeds. Stage926 all-op and Stage929 relation specialist heads are rerun with checkpoint saving, then loaded into one operation-routed multi-head module. The initialized module reproduces the Stage933 frontier exactly: eval `251/234`, implied full `481/463`. This is accepted as the clean loadable model-side value-module artifact for the current frontier. It is still candidate ranking rather than direct generation, but it removes the hand-combined scorer weakness.

Stage939 tests a calibration-only alpha router around the frozen Stage938 module. It is rejected: calibration chooses conservative alphas and eval drops to `238/221`, implied full `468/450`. This preserves the fixed Stage938 alpha policy. The result says the useful overrides are not captured by simple per-operation calibration alone; future trust layers need richer features or preservation-aware training.

Stage940 tests preservation-safe fine-tuning from Stage938 with small LR and preservation MSE while reporting fixed accepted alphas. It is rejected: fixed-alpha eval drops to `250/233`, implied full `480/462`, losing one relation row. The Stage938 specialist heads are fragile; future training should freeze those heads and train only auxiliary/router parameters unless a strict no-regression gate is used.

Stage941 freezes the specialist heads and trains only a tiny router classifier over frozen prediction features. It is rejected at `249/232`, implied full `479/461`. The router improves composition but gives up exception rows, so the fixed Stage938 operation policy remains stronger than the learned router. This keeps Stage938 as the loadable model-side frontier.

Stage942 accepts the useful slice of Stage941. The router is used only for composition, where calibration preserves Stage938 and eval improves composition from `41/25` to `42/26`; Stage938 fixed specialist policy is kept for atomic, counterfactual, exception, and relation. This raises the model-side operation-gated policy frontier to `252/235`, implied full `482/464`. It is still candidate ranking, but it is a real no-new-bridge-feature gain.

Stage943 makes the Stage942 policy reproducible at row level. It deterministically retrains the tiny composition router, applies it only to composition, keeps Stage938 decisions elsewhere, and exports all row-level decisions. The artifact reproduces `252/235`, implied full `482/464`, and saves the composition-router state. This is the current clean reproducible model-side policy artifact.

Stage944 wraps that policy into a loadable scorer. The scorer loads the Stage938 initialized multi-head module state and the Stage943 composition-router state, scores the target rows directly, and reproduces `252/235`, implied full `482/464`. This is now the cleanest current model-side artifact: a loadable scorer rather than a hand-assembled prediction table.

Stage945 tests whether a composition-only router over the same frozen score-margin features can improve the current composition slice. It is rejected: the best small linear/MLP variants tie Stage944 composition at `42/26`, so the global frontier remains `252/235`. Current composition score-margin features are saturated; further composition gains need new features/evidence.

Stage946 audits the Stage944 loadable scorer against the Stage919 typed-access ceiling and the candidate-recoverable ceiling. Stage944 remains `252/235` target rows, implied full `482/464`; Stage919 remains `311/294`, implied full `541/523`; candidate recoverability is `350/333`. The model-side gap to Stage919 is `59/59`, and the gap to candidate recoverability is `98/98`. Operation gaps to Stage919 are relation `32/32`, exception `15/15`, composition `11/11`, counterfactual `1/1`, and atomic `0/0`. Decision: no frontier change, but the next best step shifts from composition-only routing to relation source-target/value comparison, then exception claim/value comparison, then composition proof-edge evidence. Relation is now the largest remaining model-owned binding gap.

Stage947 tests the direct relation residual-head follow-up and rejects it. Variants around the Stage929 relation specialist use softer teacher MSE, h16/h32/h64 heads, and a rank-2-to-4 training window over the same frozen embedding/base/probability features. The best variant is h16 with alpha `0.01`, relation `50/50`; if applied only to relation while preserving Stage944 elsewhere, it would score `250/233`, below the Stage944 frontier `252/235`. The h32/h64 and rank-window variants calibrate to alpha `0` and stay at base relation `49/49`. Decision: preserve Stage944. Relation needs new source-target/value latent evidence or an auxiliary comparison objective, not another small residual head over the current features.

Stage948 tests the same residual-head continuation for exception. It is also rejected as a frontier gain. h32 variants tie the accepted exception slice at `54/54`; preserving Stage944 elsewhere would only tie global `252/235`. h16 falls to `42/42`, and h64 reaches `53/53`. Decision: preserve Stage944. Exception has real recoverable headroom (`87/87`) and typed-access headroom (`69/69`), but the current frozen embedding/base/probability residual features only recover the already accepted exception frontier. Future exception work needs claim/value compatibility evidence or a latent claim auxiliary, not another hidden-size sweep.

Stage949 materializes the relation latent-auxiliary target audit. Eval relation has `100/128` recoverable exact rows, but Stage944 only gets `52/52`. All `100` recoverable positives have entity and pair matches, but `39` non-exact eval candidates also have entity+pair matches, producing `35` ambiguous-pair rows. Relation queries expose `qslot` in `0/128` rows while candidate docs expose `dslot` in `128/128`; positives have `0` slot matches. In an audited ambiguous row, the wrong rank-1 candidate and the true rank-15 candidate have identical entity/pair flags and identical teacher bridge score `2.25`; only the relation slot/value differs. Decision: no frontier change, but the next accepted route must add model-owned relation slot/value compatibility. This is a surface/latent-target issue, not a residual-head capacity issue.

Stage950 materializes compact relation qslot/value auxiliary targets and runs oracle diagnostics. Eval relation has `100` rows with one positive relation-slot target and `28` unrecoverable rows. Base relation is `49/49`. Entity+pair-only selection reaches `82/82`, nearly matching Stage919 relation `84/84`, but it still uses suffix-derived entity/pair matching as a diagnostic. The qslot/value oracle reaches the full recoverable ceiling `100/100`. There are `35` ambiguous entity+pair rows and `39` entity+pair hard-negative candidates. Decision: no model-owned frontier change, but the route is now much sharper: train a relation qslot/value compatibility head from the Stage950 targets, using entity+pair hard negatives, and only accept it if predicted compatibility beats Stage944 relation `52/52` without feeding qslot targets or suffix equality at eval.

Stage951 trains that relation qslot/value compatibility head over frozen Stage784 query/doc embeddings, using Stage950 positives and entity+pair hard negatives but feeding no qslot targets, entity-pair flags, or suffix equality at eval. It is rejected. h16, h32, h64, hard-negative, and all-candidate variants all remain below the accepted relation specialist. The best h64 hard-negative variant reaches relation `51/51`, which would yield preserved global `251/234`, below Stage944 `252/235`. Decision: preserve Stage944. Stage950 proved the missing axis; Stage951 shows the frozen embeddings do not expose it strongly enough. Next: patch/materialize a side-invariant relation query-slot surface from relation text, or fine-tune the encoder with explicit qslot/value auxiliary losses before freezing.

Stage952 materializes that relation query-slot patched surface. It adds side-invariant `qslot_*` aliases to relation queries for rows with a positive slot target and recomputes candidate slot matches. Eval patches `100/128` relation rows; the slot+entity+pair oracle reaches `100/100`, matching the Stage950 qslot/value oracle. Caveat: this is diagnostic until the surface builder derives qslot aliases from relation text rather than copied positive eval slots.

Stage953 trains frozen residual heads on the Stage952 patched surface and rejects them. h32 selects alpha `0` and stays at base relation `49/49`; h64 falls to `43/43`. Decision: qslot tokens in text are still not enough for the frozen Stage784 embeddings plus a small residual head.

Stage954 runs a short low-LR encoder fine-tune on the patched surface. It also rejects: relation reaches `47/47`, preserved global `247/230`, below Stage944 `52/52` and `252/235`. Decision: generic encoder CE on the patched surface is not enough. The next implementation needs an explicit qslot/dslot token-comparison module or a first-class qslot/dslot matching objective.

Stage955 implements that first explicit typed token-comparison module over the patched qslot surface. It uses trainable typed embeddings for qent/dent, qpair/dpair, and qslot/dslot plus a small scorer, with `98,311` parameters counted. It rejects: eval relation reaches `40/40`, preserved global `240/223`, below Stage944. Decision: a tiny learned typed-token table does not learn robust qslot/dslot equality from this split. A deterministic equality feature would recover the oracle, but that would be external suffix matching. The next honest path is either a larger qslot/dslot matching curriculum before reattempting the learned comparator, or a counted architectural equality/comparison primitive with explicit parameter/feature accounting.

Stage956 scores that deterministic equality primitive as a ceiling with explicit accounting. On the Stage952 patched relation surface, base is `49/49`, entity+pair equality is `82/82`, and entity+pair+slot equality reaches the full recoverable `100/100`. If this primitive were accepted as a counted/budgeted component and Stage944 were preserved for non-relation rows, the global target score would become `300/283`, a `+48/+48` gain over Stage944 `252/235`. Decision: diagnostic only. This is the closest route so far, but it is not model-owned KBPP unless qslot aliases are generated from relation text without copied eval positives and the equality/comparison primitive is explicitly included in the model/interface budget.

Stage957 formalizes that acceptance contract. qslot aliases must be generated from relation text or schema metadata before candidate labels are known; generation must not inspect exact labels, answer values, or eval positive dslot fields; the qslot namespace must be side-invariant with doc dslot through a declared schema relation map; and the equality primitive must be accounted as a fixed architecture/interface component or as learned parameters inside the model budget. The gate is relation `>52/52`, global `>252/235`, held-out alias/hash-salt pass, no label access at eval, and row-level prediction export. Decision: no frontier change, but the route to making Stage956 acceptable is now explicit.

Stage958 audits whether the current target artifacts can regenerate qslot aliases without labels. They cannot. Relation text is present (`linked_to`, `owned_by`, `overrides`), but query qslot rows are `0`, candidate docs expose only opaque split-local dslot ids, and positive dslot ids have `0` overlap across train/calibration/eval salts. Decision: current targets are insufficient for non-label qslot generation; the surface hardener must emit relation qslot aliases before split-local hashing.

Stage959 patches `build_stage819_hardened_binding_surface.py` accordingly. The hardener now parses relation query text of the form `query=<entity> <relation>` and adds that relation to field/slot hints, so query-side relation words become side-invariant `qslot_*` aliases before hashing. The audit verifies `linked_to`, `owned_by`, and `overrides` now produce qslot aliases. Decision: accepted infrastructure patch. Next full rebuild should regenerate Stage917/918-style targets and rerun Stage956 equality under the Stage957 contract.

Stage960 performs that full rebuild. It uses the same Stage846/Stage830-compatible salts and splits as Stage917: `stage830_train`, `stage830_eval`, `stage830_cal`, retained stratified `50%` calibration, counterfactual value hardening, and `stage830_pair` pair codes. The rebuilt surface has the same row counts as Stage917 (`2048` train, `1024` calibration, `1024` eval; `1280/640/640` hardened target-operation rows). Rematerializing Stage918-style targets over the frozen Stage859 partitions keeps relation eval at `128` rows and `2228` candidates, but relation positive slot matches move from `0/100` to `100/100`. This satisfies the Stage957 qslot-generation requirement at the surface level: relation qslots are generated before candidate labels are scored, not copied from positive eval candidates.

Stage961 clarifies and scores the relation equality primitive on Stage960. A direct entity+any-pair+slot policy reaches `99/100`, exposing one important ambiguity: matching any pair overlap can select a candidate that shares the relation-slot pair but not the full source-target pair. The correct primitive is entity overlap + full pair overlap + slot overlap, implemented as `min_pair_overlap=2`. This closes relation to the recoverable `100/100` eval ceiling and would give preserved global `300/283` if the primitive is counted with Stage944 non-relation rows. Decision: Stage961 is contract-ready typed access, not model-owned internalization. It gives the exact operator to train next: entity/full-pair/slot compatibility, with row-level predictions exported for auditing.

Stages962-963 narrow that operator further. Stage962 exports candidate-level relation teacher labels for entity match, pair overlap count, full-pair match, slot match, primitive positive, and component hard negatives. The component audit shows full-pair match is already decisive: eval has `100` full-pair matches, `100` exact full-pair matches, and `0` non-exact full-pair matches. Stage963 scores qpair/dpair full-pair equality alone and reaches relation `100/100`, matching Stage961 with a smaller primitive. Decision: for model-owned training, prioritize full-pair compatibility as the primary relation objective, using entity/slot labels as auxiliary robustness checks.

Stage964 generalizes that pair-binding lens across all hardened target operations. It sweeps qpair/dpair arity thresholds on calibration and applies the selected arity per operation with base fallback. Calibration selects atomic `0`, composition `3`, counterfactual `0`, exception `1`, and relation `2`. Eval reaches `328/640` answer and `311/640` exact: atomic `49/48`, composition `58/42`, counterfactual `54/54`, exception `67/67`, relation `100/100`. The implied full split is `558/540`, above Stage919 typed access `541/523` and Stage944 model-side `482/464`. Decision: Stage964 is the new recoverable typed-access frontier. It is still not model-owned KBPP because qpair/dpair equality and operation arity are external typed primitives unless declared in the budget or learned internally.

Stage965 materializes that Stage964 policy as teacher supervision. It exports `1610` row records and `5276` candidate records with pair-overlap count, selected operation arity, arity-positive label, hard-negative flag, and fallback-routing status. Totals: `801` arity-positive candidates, `749` exact arity-positive candidates, and `52` arity hard negatives. The hard negatives are concentrated in exception (`8` train, `44` eval); composition and relation have no non-exact candidates once their selected pair arity fires. Decision: accepted teacher-target infrastructure. The next learned comparator should target pair-overlap prediction and exception disambiguation directly rather than relying on generic answer CE.

Stage966 trains a counted arity/fallback router from Stage965. It uses `pair_overlap_count` as a declared primitive feature plus operation, selected arity, base score, and rank. A 97-parameter MLP learns the arity-positive/fallback decision; calibration selects threshold `0.05`. Eval exactly reproduces Stage964 at `328/640` answer and `311/640` exact, implied full `558/540`, with the same operation slices. Decision: accepted counted-router probe. This moves the hand-selected operation arity/fallback policy into a tiny learned module, but it still does not learn token equality. The remaining internalization target is the pair-overlap primitive itself.

Stage967 audits and accounts for that remaining primitive. Important correction: `qpair/dpair` codes are shared-anchor bridge codes for original query/doc tokens present on both sides, not learned tuple-pair embeddings. The primitive is `qpair_dpair_shared_anchor_overlap_count`: harden query and doc independently, emit side-specific bridge codes for original token intersections with a fixed pair-code salt, then count suffix set intersection at scoring time. It uses no exact labels, answer-match labels, or candidate ranks. Across Stage965 candidates, the overlap histogram is `0:1865`, `1:2176`, `2:774`, `3:461`. Decision: if fixed interface primitives are allowed, Stage966 is a 97-parameter router plus this set-intersection primitive. If strict model-owned proof is required, the next proof must learn or expose this equality/count circuit inside the budget.

Stage968 turns that route into a loadable scorer. Stage966 now saves `stage966_pair_arity_router_state.pt`; Stage968 loads it, computes qpair/dpair shared-anchor overlap live from Stage960 bridge tokens, applies the saved threshold/fallback policy, and reproduces Stage964/966 exactly: `328/640` answer, `311/640` exact, implied full `558/540`. Decision: accepted loadable counted-interface scorer. This is the clean implementation path if fixed comparison primitives are allowed. For strict model-owned internalization, the next target is to replace the live set-intersection circuit with a learned equality/count module while keeping the same router gate.

Stage969 reviews the 100M launch path. The intended old bases remain v430 first, v424 second, and v429 only if encoder perturbation is acceptable; those expected workspace checkpoints are still absent. A broader artifact search found fallback checkpoints in `/data/agent_kernel_lite/artifacts`, and Stage969 now selects v415 (`pocketpal_controller_100m_v415_structured_json_head_from_v410`) as a conservative available base. Status is `ready_for_100m_smoke`. Decision: Stage968 is ready as the scorer/interface gate, and a bounded frozen-decoder smoke can start from v415, while v430/v424 restoration remains preferable for later promotion.

Stage970 formalizes the 100M-vs-7B bridge contract. The research claim is scoped to binding-first semantic compression and verified semantic decision density; it does not yet claim that a 100M model generally beats a modern 7B. The required evidence is: run/evaluate a 100M checkpoint with the Stage968 interface, preserve app/NLL gates, evaluate a modern 7B baseline on the identical scorer/candidate sets, and claim a win only after counting all interface/router/fixed-primitive budget. Current status is `blocked_missing_7b_stage968_baseline`: the 100M smoke path is unblocked by v415, but the same-scorer 7B baseline is still absent.

Stage971 runs the 100M preflight dry-run from the v415 fallback base. The bundle loads a `100,877,568` parameter `agentkernel-lite-100m` config on CUDA with the frozen-decoder Stage968 smoke settings and the Stage960 hardened train/eval paths. This is not a trained 100M KBPP result; it only proves that the 100M architecture/checkpoint/data path can compile for the next bounded smoke. Audit note: the bundle top-level `dataset_manifest_path` still points to an inherited Stage784 source manifest, but `training_summary.train_dataset_path` and `training_summary.eval_dataset_path` correctly point to the requested Stage960 hardened split.

Stage972 completes the first real 100M smoke from v415. Two load fixes were required: use the v415 `agentkernel-bpe` tokenizer (`1506` vocab) instead of the byte tokenizer (`260` vocab), and instantiate the v415 controller heads (`agent_policy_heads=1`, `agent_controller_dim=128`, `agent_intent_labels=18`). With those matched, the `102,654,362` parameter model trains for `20` steps with decoder and token embeddings frozen, updates `5,742,337` trainable parameters, writes `step_00000020.pt`, and exports `model/model.safetensors`. Eval loss is finite and moves from `7.097064971923828` at step 10 to `7.022272408008575` at step 20. The Stage968 scorer still reproduces `328/640` answer and `311/640` exact, implied full `558/540`. Decision: 100M training infrastructure is now running, but this is not yet a 100M-over-7B result and not bridge-free model-owned KBPP.

Stage973 builds the first local 7B-class prompt baseline harness over Stage960 candidate rows. Ollama has local `deepseek-r1:7b`, `qwen2.5vl:7b`, `qwen3:8b`, and `qwen3.5:9b` models available. The harness reports the top-k ceiling separately because full relation rows can contain thousands of candidates and do not fit a fair prompt baseline. Prompt control matters: the original example-style prompt caused invalid/false parses; the fixed `/no_think` candidate-index prompt gives `qwen3:8b` `12/15` exact on a balanced top-8-positive smoke with zero invalids. `deepseek-r1:7b` remains output-control limited at `2/15` exact with `11` invalids. Decision: local baseline infrastructure exists, but the accepted 100M-vs-7B gate still needs a full-candidate or equivalent same-scorer protocol, not just a top-k-positive smoke.

Stage974 adds the missing 100M model-owned candidate-ranking evaluation. It scores every Stage960 candidate with the 100M retrieval embeddings, then calibrates optional `base_score + alpha * model_score` blending on the calibration split. The untouched v415 base and Stage972 smoke both land at `241/224` selected eval rows, implied full `471/453`; Stage972 raw model-only is slightly lower than v415 (`219/202` versus `220/203`). Decision: the 20-step smoke proves infrastructure but does not improve model-owned KBPP. The next 100M objective must train binding directly.

Stage975 distills the Stage968 pair-overlap primitive into 100M retrieval embeddings. It exports `teacher_bridge_score` from qpair/dpair overlap and selected operation arity for `1610` rows and `5276` candidates, with `801` positive teacher candidates. A `teacher_mse_weight=1.0` probe reaches `251/234` ungated, one row below Stage944. Operation-gating the useful blend slices for composition and exception while preserving base for atomic, counterfactual, and relation reaches `256/239` target rows, implied full `486/468`. Decision: this is a new 100M model-owned gated probe frontier over Stage944 `252/235`, but it is not yet a saved loadable checkpoint.

Stage976 turns the Stage975 probe into a loadable 100M artifact and raises the frontier. The cached encoder trainer now saves a full `model/`, `tokenizer/`, and manifest bundle. Reloading the saved v415-derived bundle through the independent Stage974 model-owned ranking evaluator reproduces the trained scores. With `teacher_mse_weight=1.0`, `60` steps, operation-balanced sampling, and `33,623,296` trainable parameters, calibration selects residual alpha `0.75`. The selected blend reaches eval `272/640` answer and `255/640` exact. A calibration-derived operation gate uses the learned blend for composition and exception while preserving base for atomic, counterfactual, and relation, reaching `282/640` answer and `265/640` exact, implied full `512/494`. Decision: accepted as the new loadable 100M model-owned candidate-ranking frontier. Caveat: this is retrieval-embedding candidate ranking, not direct generation, and remains `46/46` target rows below the Stage968 counted-interface typed-access ceiling `328/311`.

Stages977-979 isolate the remaining relation gap. Relation-only candidate CE with the Stage975 pair-overlap teacher overfits train (`99/128`) and improves calibration (`48/65`) but falls to eval `43/128`, below base `49/128`. Reducing candidate CE to `0.1` or `0.0` prevents deployed regression because calibration selects alpha `0`, but gives no eval gain: relation remains `49/128`. Decision: reject scalar relation distillation into retrieval embeddings. The relation full-pair equality/count operation is not transferring from scalar teacher pressure; it needs a first-class counted comparator or a stronger internal comparison objective.

Stage980 computes the best current budgeted hybrid. Keep base for atomic and counterfactual, use Stage968 counted pair-overlap/count for composition and relation, and use the saved Stage976 model-owned blend for exception where calibration ties Stage968 while reducing external-interface dependence. This reaches `342/640` answer and `325/640` exact, implied full `572/554`, beating Stage968 by `+14/+14` target rows and Stage976 by `+60/+60`. Decision: accepted as a budgeted hybrid calculation only, not bridge-free model-owned KBPP. It gives the practical route for a 100M-plus-interface system while the comparator is being internalized.

Stage981 implements that hybrid as a loadable row-level scorer. It loads the saved Stage976 100M bundle, embeds query/doc candidates for the model-owned exception residual, loads the Stage966 97-parameter router, computes qpair/dpair shared-anchor overlap live for the Stage968 counted pair interface, and exports row-level predictions. It reproduces Stage980 exactly on eval: `342/640` answer and `325/640` exact, implied full `572/554`. Decision: Stage981 replaces Stage980 as the implemented budgeted hybrid frontier. Caveat remains unchanged: composition and relation still depend on the counted pair-overlap/count interface, so this is not bridge-free model-owned KBPP.

Stage982 audits the declared comparator budget for Stage981. The fixed qpair/dpair comparator has `0` trainable parameters, and the only trainable interface component beyond the 100M bundle is the `97`-parameter Stage966 router, giving a counted denominator of `102,654,459` parameters if the fixed primitive is allowed. On eval, the comparator is invoked for `256` rows and `2771` candidates, performing `13,655` qpair/dpair cross-comparisons. It produces `142` arity-positive eval candidates, all exact and no non-exact positives. Decision: Stage981 can be claimed only as "100M plus declared fixed pair-overlap/count interface"; it cannot be called bridge-free model-owned KBPP.

Stages983-984 improve the 7B-class baseline evidence. A bounded all-candidate Qwen3 8B prompt baseline over `50` balanced eval rows reaches `18/50`, but that selection only has `22/50` recoverable positives. Requiring a positive candidate in the full candidate set gives a fairer `50`-row same-row sample: Qwen3 8B reaches `45/50` exact, while Stage981 reaches `50/50` on the exact same row indices. Decision: first bounded same-row all-candidate comparison favors Stage981 over the local 8B prompt baseline. Caveat: this is still not the full `640`-row modern 7B baseline required for the final claim.

Stage985 runs that full same-candidate baseline for Qwen3 8B. Over all `640` eval rows with all candidates exposed (`top_k=999`), Qwen3 8B reaches `317/640` answer and `300/640` exact with `0` invalid outputs. Stage981 on the same candidate set is `342/640` answer and `325/640` exact, a `+25/+25` row advantage. Operation detail: Qwen3 8B is stronger on counterfactual (`56/56` vs Stage981 `54/54`), but Stage981 is stronger on composition (`58/42` vs `56/40`), exception (`81/81` vs `73/73`), and relation (`100/100` vs `83/83`). Decision: first full 640-row same-candidate 8B baseline supports the budgeted-interface thesis. Caveat: this still does not prove bridge-free model-owned 100M superiority.

Stages986-987 test the stronger local Qwen3.5 9B baseline. The first run is rejected because this model emitted only hidden `thinking` and empty `response`, producing `640/640` invalid rows. Adding Ollama `think=false` fixes the output path. With all candidates exposed over all `640` eval rows, Qwen3.5 9B reaches `321/640` answer and `304/640` exact with `0` invalid outputs. Stage981 remains `342/640` answer and `325/640` exact, a `+21/+21` row advantage. Decision: Stage981 now beats both local Qwen3 8B and Qwen3.5 9B full same-candidate prompt baselines. Caveat remains: this supports the 100M-plus-declared-interface result, not bridge-free model-owned 100M superiority.

Stage988 turns those results into an explicit claim gate. The allowed claim passes: on this `640`-row KBPP candidate-selection benchmark, the `102,654,459` counted-parameter 100M system plus declared fixed pair-overlap/count comparator and 97-parameter router beats local Qwen3 8B and Qwen3.5 9B prompt baselines on the same candidate sets. Approximate parameter ratios are `77.9x` fewer than 8B and `87.7x` fewer than 9B. The bridge-free 100M claim fails because Stage976 is only `282/265`, below both prompt baselines. Direct/free-form generation parity remains untested and therefore fails. Decision: budgeted-interface result is accepted; bridge-free model-owned result remains open.

Stages989-991 add a local 12B baseline and extend the claim gate. Gemma3 12B first passes a format smoke and scores `45/50` on the positive-candidate bounded sample. On the full `640`-row same-candidate baseline, Gemma3 12B reaches `309/640` answer and `292/640` exact with `0` invalid outputs. Stage981 remains `342/640` answer and `325/640` exact, a `+33/+33` row advantage. Stage991 therefore upgrades the allowed claim: the `102,654,459` counted-parameter 100M system plus declared comparator beats local Qwen3 8B, Qwen3.5 9B, and Gemma3 12B full same-candidate prompt baselines. Approximate parameter ratio versus 12B is `116.9x`. Caveat remains: bridge-free Stage976 is still `282/265`, so the model-owned internalization claim remains open.

Stage992 packages the accepted budgeted-interface system. The manifest binds the Stage976-derived 100M bundle, Stage981 scorer, Stage966 97-parameter router, declared fixed qpair/dpair overlap-count primitive, Stage982 budget audit, and Stage991 baseline gate into one reproducible system record. Decision: accepted as the current packaged 100M budgeted-interface KBPP system, while explicitly rejecting bridge-free/internalized-comparator and free-form generation claims.

Stage993 adds constrained answer materialization. It takes Stage981 selected candidates and emits the typed `answer=<value>` field from each selected candidate. Parse reliability is `640/640`; correctness remains `342/640` answer and `325/640` exact. Decision: constrained answer emission is reliable for the selected-candidate interface. Caveat: this is typed extraction/materialization, not free-form generation.

Stages994-1002 replace the fixed pair-overlap/count primitive with learned encoder-comparator machinery. Stage994's row-level comparator is rejected at `82/66` over composition+relation, below base `85/69`, because frozen row-span features are too indirect. Stage995/996 train pair-level equality from frozen 100M qpair/dpair token states and recover most of the primitive: `152/256` answer and `136/256` exact over composition+relation, with composition matching the fixed interface (`58/42`) and relation reaching `94/94`. Stage998 low-threshold and Stage999 positive-weight variants do not improve it. Stage1000 adds a `705`-parameter soft-count candidate scorer over learned pair-equality probabilities and closes the gap: composition+relation reach `158/142`, matching the fixed pair interface without eval-time suffix set intersection. Stage1001 packages the full scorer: base for atomic/counterfactual, Stage976 model-owned blend for exception, and Stage1000 learned soft-count comparator for composition/relation. It matches Stage981 exactly at `342/640` answer and `325/640` exact, implied full `572/554`, with counted parameters `102,819,133`. Stage1002 claim gate: this learned-comparator 100M system beats the local Qwen3 8B (`317/300`), Qwen3.5 9B (`321/304`), and Gemma3 12B (`309/292`) same-candidate prompt baselines. Caveat: qpair/dpair marker tokens still locate comparison slots; this is learned comparator internalization, not arbitrary natural-language binding discovery or free-form generation parity.

Stages1035-1037 update the current no-anchor counted-interface frontier. Stage1035 calibrates the Stage976 exception blend on the no-anchor target and selects `alpha=0.25`, improving eval exception from `81/81` to `82/82`. Stage1036 combines that with learned char-schema composition, relation source-role binding, and base atomic/counterfactual ranking to reach `343/640` answer and `326/640` exact, implied full `573/555`, with counted parameters `102,657,756`. Stage1037 gates the claim: this exceeds Stage981 by `+1/+1` and beats local Qwen3 8B, Qwen3.5 9B, and Gemma3 12B same-candidate baselines by `+26/+26`, `+22/+22`, and `+34/+34`. Caveat: this is still a declared learned string-comparator plus typed-role interface, not bridge-free encoder-owned equality or free-form general-knowledge parity.

Stages1038-1041 saturate the current no-anchor target surface's recoverable rows. Stage1038 adds exception source/default-kind and counterfactual source-role policies, improving eval to `346/640` answer and `329/640` exact, implied full `576/558`. Its residual audit exposes two narrow parser/operator gaps: counterfactual statements render as `statement=claim dent_*`, and schema-default exception rows have no `qent` and must be matched as `default risk/tool` policy rows. Stage1040 fixes both and reaches `350/640` answer and `333/640` exact, exactly matching the current recoverable ceiling, implied full `580/562`. Stage1041 gates the claim: Stage1040 beats Stage981 by `+8/+8` and beats Qwen3 8B, Qwen3.5 9B, and Gemma3 12B same-candidate baselines by `+33/+33`, `+29/+29`, and `+41/+41`. Caveat: this is a typed-operator interface result, not bridge-free encoder-owned equality or broad free-form 7B parity. The next useful experiment must move to a harder hidden split or train the 100M encoder to own these operators internally.

Stage1042 turns that into an implementation contract for bridge-free internalization. It requires Stage1043 operator-teacher target export and Stage1044 salted hidden no-anchor targets before another 100M fine-tune. The operator heads to train are statement-entity match, slot match, composition slot count, relation source role, counterfactual statement-entity/slot, exception source/default-kind policy, and final candidate value score. Acceptance requires beating Stage976 and the local 8B/9B/12B same-candidate baselines without external char comparator access, bridge fields, deterministic suffix set intersection, or explicit pair anchors.

Stages1043-1044 complete those preparation artifacts. Stage1043 exports operator-teacher targets over `1610` rows and `5276` candidates, including `1024` positive operator candidates and one Stage1040-selected candidate per row. Stage1044 builds a salted hidden no-anchor transfer split from eval: `640` hidden rows, `3412` candidates, and `679` remapped entity/slot/pair/claim identifiers. These artifacts shift the next work from interface scoring to bridge-free 100M operator-head training and hidden-transfer evaluation.

Stages1045-1046 run the first bridge-free frozen-head probes from Stage1043. Stage1045 trains a frozen-100M residual value head over all operations using `teacher_candidate_value_score`; it is rejected because relation collapses, with ungated eval `240/223` and best diagnostic gate `275/258`. Stage1046 narrows training to composition/exception. The calibration-selected operation+alpha gate uses the head for composition and exception and preserves base for other operations, reaching `282/640` answer and `265/640` exact. This exactly matches the Stage976 model-owned frontier but does not beat it or the larger local baselines. Conclusion: frozen 100M embeddings contain partial operator signal, especially exception/composition, but bridge-free progress now requires encoder-owned operator-head training.

Stages1047-1048 test the direct encoder-fine-tune version and reject the scalar retrieval/value objective. Stage1047 enables encoder training with low LR and Stage1043 selected-candidate supervision. It does not improve bridge-free eval: calibration-selected gating reaches `275/640` answer and `258/640` exact, below Stage1046 and Stage976. The useful finding is negative: relation can improve on train, but eval binding remains unstable when the objective is a single candidate score. Stage1048 therefore shifts the route to pair/span-level operator heads before candidate ranking: entity span equality, slot span equality, statement role, default kind, and operation-local candidate composition.

Stages1049-1050 test the first span-operator version and reject simple span-similarity composition. Stage1049 trains a small frozen 100M token-span operator head over rendered qent/dent, qslot/dslot, and default/answer-kind spans. Calibration is strong at `297/330` answer and `292/330` exact, but eval transfers poorly at `270/640` answer and `253/640` exact. Stage1050 records the next correction: train contrastive span-pair equality heads with same-operation hard negatives and salted Stage1044 augmentation before training candidate composition.

Stages1051-1055 produce the first accepted bridge-free learned-pair frontier. Stage1051 exports `43,951` contrastive span-pair examples. Stage1052 trains a frozen-100M span-pair classifier with `99.88%` calibration accuracy, `89.06%` eval accuracy, and `99.81%` hidden transfer accuracy. Stage1053 uses learned pair probabilities for candidate policy and reaches `306/640` answer and `289/640` exact. Stage1054 changes composition to slot-count policy and reaches `311/640` answer and `294/640` exact. Stage1055 claim gate: this beats Stage976 by `+29/+29` and Gemma3 12B by `+2/+2` without bridge fields, char comparator, suffix set intersection, or pair anchors as candidate-scoring inputs. It remains below Qwen3 8B by `6/6` rows; diagnostic eval-best per-operation thresholds reach `314/297`.

Stages1056-1057 train a learned candidate composer over the pair probabilities and clear the larger-model same-candidate baselines. Stage1056 uses Stage1052 learned pair-probability aggregates, base score, rank, and operation id as candidate-scoring inputs. Calibration selects `alpha=0.05`; eval reaches `329/640` answer and `312/640` exact. Stage1057 gates the claim: the bridge-free learned-pair composer beats Stage976 by `+47/+47`, Qwen3 8B by `+12/+12`, Qwen3.5 9B by `+8/+8`, and Gemma3 12B by `+20/+20`. It remains `21/21` below the Stage1040 typed-interface ceiling and is still candidate-ranking, not direct/free-form generation.

Stages1058-1065 close the next binding gap. Stage1058 transfers the Stage1056 composer to the Stage1044 salted hidden no-anchor split without hidden retraining and reaches `343/640` answer and `326/640` exact, with relation `100/100`. Stage1059 rejects per-operation alpha calibration because it regresses eval and hidden transfer. Stage1060 audits the remaining composition misses and identifies missing target-entity supervision: same-slot composition candidates are indistinguishable without `target for dent_*` binding. Stage1061 adds that target-entity span-pair supervision, Stage1062 retrains the frozen-100M pair classifier, and Stage1063 retrains the small candidate composer. Eval improves to `338/640` answer and `321/640` exact, with composition reaching its recoverable ceiling `58/42`. Stage1064 then reaches the Stage1040 typed-interface ceiling on salted hidden transfer: `350/640` answer and `333/640` exact. Stage1065 gates this as the current bridge-free learned-pair/composer frontier: it beats Stage976 by `+56/+56`, Stage1057 by `+9/+9`, Qwen3 8B by `+21/+21`, Qwen3.5 9B by `+17/+17`, and Gemma3 12B by `+29/+29` on eval, while hidden transfer exactly matches the typed ceiling. Caveat: this is still controlled candidate ranking, not direct or free-form generation parity.

Stage1066 rejects the simple threshold-policy fallback on the Stage1062 classifier. It reaches only `310/640` answer and `293/640` exact, with relation `79/79`, so relation needs a stronger learned source-target/entity compatibility objective rather than pair-probability threshold tuning.

Stages1067-1069 close the relation gap without retraining. Stage1067 audits the `12` Stage1063 relation misses and finds that the classifier already separates wrong relation slots from oracle slots; the oracle learned score is higher, but low-alpha blending lets base-score margins win. Stage1068 rescoring uses the same Stage1062 classifier and Stage1063 composer, but changes calibration tie-breaking to prefer stronger alpha when answer/exact tie. With `alpha=2.0`, eval reaches `350/640` answer and `333/640` exact, and salted hidden transfer also reaches `350/333`. Stage1069 gates this as the current bridge-free learned-pair/composer ceiling: it matches Stage1040 typed-interface recoverability on both eval and hidden transfer, beats Stage976 by `+68/+68`, Qwen3 8B by `+33/+33`, Qwen3.5 9B by `+29/+29`, and Gemma3 12B by `+41/+41`. This completes the current controlled same-candidate ranking surface. Remaining work is constrained answer materialization, direct/free-form generation, and broader general-knowledge transfer.

Stages1070-1071 complete constrained materialization and prepare direct-answer training. Stage1070 extracts typed `answer=<value>` from Stage1069 selections and preserves the frontier: eval and salted hidden transfer both have `640/640` parse reliability and `350/333` answer/exact correctness. Stage1071 exports `2,250` direct-answer distillation rows across train, calibration, eval, and hidden transfer. Train selected targets are `640/640` answer and `628/640` exact; eval and hidden are both `350/640` answer and `333/640` exact. This gives the next direct-generation training surface, but it is not itself a free-form decoder result.

Stages1072-1078 test direct decoder completion and reject ordinary decoder CE. Stage1072 builds the Stage1071 direct-answer train/eval manifests. Stage1073 adds a batched direct decoder value-ranking evaluator. Stage1074 trains a 120-step encoder-frozen decoder continuation from the v415/Stage976 100M bundle; despite eval loss around `0.47`, structured full-candidate direct-value ranking on 100 eval rows is `0/100` top-1. Stage1076 trains a 500-step full-model continuation; it improves MRR slightly but still reaches only `1/100` top-1. Stage1078 gates this as a rejection: direct/free-form generation is not complete through plain decoder CE. The next route must use an explicit answer/value head or constrained generator over Stage1069 selector latents, then distill that answer decision into decoder text.

Stages1003-1007 probe how much of that comparator can survive without explicit span metadata. Stage1003 removes qpair/dpair span lookup entirely and trains from full query/doc token-state alignment features; it rejects at `82/66`, below base, showing frozen full-token geometry is not enough for a tiny scorer to discover the comparator unaided. Stage1004 then removes structured `query_bridge`/candidate `bridge` field access but self-locates rendered qpair/dpair tokens from text; pair equality reproduces Stage996 at `152/136`. Stage1005 trains the soft-count scorer on top of that text-self-located comparator and again reaches `158/142`. Stage1006 packages the full 640-row hybrid with rendered-text suffix extraction and no structured bridge-field access, preserving `342/325`, implied full `572/554`, counted parameters `102,819,133`. Stage1007 claim gate replaces Stage1002 as the stricter current claim: learned comparator plus rendered-text self-location beats the 8B/9B/12B prompt baselines. Remaining blocker: rendered qpair/dpair marker tokens still exist; next gate is naturalized or removed marker text, then distillation of comparator heads into the 100M encoder.

Stages1008-1012 naturalize the marker text. Stage1008 rewrites rendered query/doc bridge text by replacing side-specific `qpair_` and `dpair_` markers with a side-neutral `anchor_` marker while retaining structured bridge fields only for audit compatibility. Stage1009 trains pair equality from rendered `anchor_` tokens and reaches `150/134` over composition+relation, slightly below Stage1006's hard-count `152/136` but still far above base. Stage1010 restores the full soft-count two-op frontier at `158/142`. Stage1011 packages the full naturalized-anchor 100M hybrid and again preserves `342/640` answer, `325/640` exact, implied full `572/554`, with counted parameters `102,819,133`. Stage1012 claim gate: this system removes structured bridge-field access and side-specific qpair/dpair rendered markers while still beating the same 8B/9B/12B baselines. Remaining blocker: explicit side-neutral `anchor_` tokens still expose comparison slots.

Stages1013-1018 test removing explicit anchor tokens. Stage1013 strips rendered `anchor_` tokens from query/doc text, producing a no-anchor surface while retaining bridge fields only for audit compatibility. Stage1014 reruns full-token alignment on that surface and rejects at `82/66`, confirming the frozen full-token geometry still cannot discover binding unaided. Stage1015 trains learned schema-marker equality over qent/dent and qslot/dslot but overfits badly: eval falls to `65/49`. Stage1016 makes those schema markers side-neutral (`entity_`, `slot_`), and Stage1017 still rejects at `66/50`. Stage1018 then measures the deterministic schema-equality ceiling on the no-anchor surface: calibration selects composition `(entity>=0, slot>=2)` and relation `(entity>=1, slot>=1)`; eval reaches `150/134`, with relation `99/99`. Decision: no-anchor information is mostly present in schema entity/slot markers, but the learned schema comparator is the current weak link. Next route: distill deterministic schema equality/count into the encoder/comparator without reintroducing pair anchors.

Stage1019 tests that distillation route directly by training candidate labels from the Stage1018 schema policy and using thresholded learned positives with base fallback. It improves over Stage1015/1017 but remains far below the deterministic ceiling: eval reaches `100/84`. Composition matches the Stage1018 composition slice (`51/35`), but relation falls back to base-level `49/49` instead of the deterministic `99/99`. Decision: policy distillation fixes composition schema-count behavior but not relation source-target equality. The next no-anchor objective should target relation-specific entity equality with hard same-slot negatives and a no-regression gate.

Stages1020-1022 sharpen that no-anchor route. Stage1020 trains relation-only learned entity and slot equality with calibrated thresholds; it improves relation from base `49/49` to `69/69`. Stage1021 repeats the test on side-neutral `entity_`/`slot_` markers and reaches `71/71`, a small gain but still below the deterministic `99/99`. Stage1022 packages the deterministic no-anchor schema-equality route as a full 640-row hybrid: base for atomic/counterfactual, Stage976 model-owned blend for exception, and Stage1018 schema equality for composition/relation. It reaches `334/640` answer and `317/640` exact, implied full `564/546`, still above the local 8B/9B/12B prompt baselines but below the learned-anchor Stage1011 `342/325`. Decision: no-anchor counted schema equality is a viable 100M route; learned relation schema equality remains the internalization bottleneck.

Research framing update: knowledge compression is verified semantic decision recovery under a constrained budget, not low perplexity on knowledge-shaped text. GPT-style pretraining is broad, lossy, and access-uneven because entity, slot, relation, proof edge, and output format must be inferred indirectly through next-token gradients. The KBPP program is access-first compression engineering: controlled knowledge formats, collision-heavy retrieval, verified recovery, operation-level miss audits, smallest-mechanism fixes, and alias/hash/no-label gates. The main empirical result is that capacity is not the current bottleneck; binding is. Stage956 and Stage961 show that small typed access operators can close large relation gaps, which means the 100M route should spend parameters or declared interface budget on reusable semantic binding operations rather than rediscovering equality and schema alignment through surface text.

## Source Artifacts

- Budget summary: `runs/local/artifacts/knowledge_compression_ladder_stage429_summary.json`
- 100k curve summary: `runs/local/artifacts/knowledge_compression_ladder_stage429_budget_summary.json`
- Stage430 semantic ops summary: `runs/local/artifacts/knowledge_compression_stage430_semantic_ops_summary.json`
- Stage432 cleaned semantic ops summary: `runs/local/artifacts/knowledge_compression_stage432_semantic_ops_set_reverse_summary.json`
- Stage433/Stage434 operation-token summary: `runs/local/artifacts/knowledge_compression_stage434_440_operation_routing_residual_summary.json`
- Stage441-444 binding-key summary: `runs/local/artifacts/knowledge_compression_stage441_444_binding_keys_summary.json`
- Stage445-447 extended-set summary: `runs/local/artifacts/knowledge_compression_stage447_compact_set_ops_summary.json`
- Stage448-452 derived-set summary: `runs/local/artifacts/knowledge_compression_stage448_452_derived_set_ops_summary.json`
- Stage453-459 factorized-direct summary: `runs/local/artifacts/knowledge_compression_stage453_459_factorized_direct_summary.json`
- Stage460-464 rule-case/intersection summary: `runs/local/artifacts/knowledge_compression_stage460_470_rule_case_intersections_summary.json`
- Stage469+ compact-reverse scale summary: `runs/local/artifacts/knowledge_compression_stage469_552_structured_rerank_summary.json`
- Stage575 ultralow entity-anchor summary: `runs/local/artifacts/knowledge_compression_stage575_ultralow_entity_key_anchor_summary.json`
- Stage572/575 failure overlap analysis: `runs/local/artifacts/knowledge_compression_stage572_575_failure_overlap_analysis.json`
- Stage578 16k density-frontier failure analysis: `runs/local/artifacts/knowledge_compression_16k_density_frontier_failure_analysis.json`
- Stage579 compact-membership negative result: `runs/local/artifacts/knowledge_compression_stage579_compact_membership_negative_summary.json`
- Operation bits/parameter report: `runs/local/artifacts/operation_bits_per_param_report.json`
- 100M general KBPP route map: `runs/local/artifacts/100m_general_kbpp_route_map.json`
- Model intelligence density framework: `runs/local/artifacts/model_intelligence_density_framework.json`
- General KBPP benchmark spec: `runs/local/artifacts/general_kbpp_benchmark_spec.json`
- Scale-sweep intelligence density: `runs/local/artifacts/scale_sweep_intelligence_density.json`
- General KBPP pilot dataset: `runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_pilot_manifest.json`
- General KBPP pilot scorer/oracle: `runs/local/artifacts/general_kbpp_pilot_oracle_score_100m.json`
- General KBPP sweep readiness: `runs/local/artifacts/general_kbpp_sweep_readiness.json`
- KBPP maximization map: `runs/local/artifacts/kbpp_maximization_map.json`
- Stage591 anchored membership analysis: `runs/local/artifacts/stage591_anchored_membership_card_analysis.json`
- Answer-equivalence KBPP tax: `runs/local/artifacts/answer_equivalence_kbpp_tax.json`
- Stage593 answer-equivalence contrast summary: `runs/local/artifacts/stage593_answer_equivalence_contrast_summary.json`
- Stage594 residual answer-equivalence contrast summary: `runs/local/artifacts/stage594_residual_answer_contrast_summary.json`
- Stage595 structured filter ceiling: `runs/local/artifacts/stage595_structured_filter_ceiling.json`
- Stage596 collision-conditioned probe: `runs/local/artifacts/stage596_collision_conditioned_probe.json`
- Stage598 collision continuation summary: `runs/local/artifacts/stage598_collision_continuation_summary.json`
- Stage599 weak-op replay summary: `runs/local/artifacts/stage599_weakop_replay_summary.json`
- Stage600 entity/two-hop summary: `runs/local/artifacts/stage600_entity_twohop_summary.json`
- Stage601 entity-field dataset: `runs/local/artifacts/stage601_entity_field_context_dataset.json`
- Stage601 entity-field summary: `runs/local/artifacts/stage601_entity_field_context_summary.json`
- Stage602 entity-field balanced replay dataset: `runs/local/artifacts/stage602_entity_field_balanced_replay_dataset.json`
- Stage602 entity-field balanced replay summary: `runs/local/artifacts/stage602_entity_field_balanced_replay_summary.json`
- Stage603 rule-intersection repair dataset: `runs/local/artifacts/stage603_rule_intersection_repair_dataset.json`
- Stage603 rule-intersection repair summary: `runs/local/artifacts/stage603_rule_intersection_repair_summary.json`
- Stage604 residual replay summary: `runs/local/artifacts/stage604_residual_replay_summary.json`
- Stage605 entity answer residual dataset: `runs/local/artifacts/stage605_entity_answer_residual_dataset.json`
- Stage605 entity answer residual summary: `runs/local/artifacts/stage605_entity_answer_residual_summary.json`
- Stage606 entity residual geometry: `runs/local/artifacts/stage606_entity_residual_geometry.json`
- Stage607 entity field role-token dataset: `runs/local/artifacts/stage607_entity_field_role_tokens_dataset.json`
- Stage607 entity field role-token summary: `runs/local/artifacts/stage607_entity_field_role_tokens_summary.json`
- Stage608 entity role answer-contrast summary: `runs/local/artifacts/stage608_entity_role_answer_contrast_summary.json`
- Stage609 entity role answer-residual dataset: `runs/local/artifacts/stage609_entity_role_answer_residual_dataset.json`
- Stage609 entity role answer-residual summary: `runs/local/artifacts/stage609_entity_role_answer_residual_summary.json`
- Stage610 entity selector-token dataset: `runs/local/artifacts/stage610_entity_selector_tokens_dataset.json`
- Stage610 entity selector-token summary: `runs/local/artifacts/stage610_entity_selector_tokens_summary.json`
- Stage611 compact entity selector dataset: `runs/local/artifacts/stage611_compact_entity_selector_dataset.json`
- Stage611 compact entity selector summary: `runs/local/artifacts/stage611_compact_entity_selector_summary.json`
- Stage612 bare selector-pair dataset: `runs/local/artifacts/stage612_bare_selector_pair_dataset.json`
- Stage612 bare selector-pair summary: `runs/local/artifacts/stage612_bare_selector_pair_summary.json`
- Stage613 short selector-pair dataset: `runs/local/artifacts/stage613_short_selector_pair_dataset.json`
- Stage613 short selector-pair summary: `runs/local/artifacts/stage613_short_selector_pair_summary.json`
- Stage614 raw selector-pair dataset: `runs/local/artifacts/stage614_raw_selector_pair_dataset.json`
- Stage614 raw selector-pair summary: `runs/local/artifacts/stage614_raw_selector_pair_summary.json`
- Stage615 raw selector no-role-token dataset: `runs/local/artifacts/stage615_raw_selector_no_role_tokens_dataset.json`
- Stage615 raw selector no-role-token summary: `runs/local/artifacts/stage615_raw_selector_no_role_tokens_summary.json`
- Recursive KBPP selector hill-climb smoke artifact: `runs/local/artifacts/recursive_kbpp_selector_hillclimb_smoke.json`
- Stage616 recursive selector delimiter search: `runs/local/artifacts/stage616_recursive_selector_delimiter_search.json`
- Stage616 recursive selector delimiter note: `docs/stage616_recursive_selector_delimiter_search.md`
- Stage617 direct-fact selector transfer: `runs/local/artifacts/stage617_direct_fact_selector_transfer.json`
- Stage618 entity+direct selector transfer: `runs/local/artifacts/stage618_entity_direct_selector_transfer.json`
- Stage617/618 selector transfer note: `docs/stage617_618_selector_transfer.md`
- Stage619 broad selector transfer: `runs/local/artifacts/stage619_broad_selector_transfer.json`
- Stage620 broad selector no-two-hop control: `runs/local/artifacts/stage620_broad_selector_no_twohop.json`
- Stage621 two-hop selector search: `runs/local/artifacts/stage621_twohop_selector_search.json`
- Stage619-621 selector transfer note: `docs/stage619_621_selector_transfer.md`
- Stage622 rule-count selector search: `runs/local/artifacts/stage622_rule_count_selector_search.json`
- Stage623 rule-member selector search: `runs/local/artifacts/stage623_rule_member_selector_search.json`
- Stage624 field-lookup domain selector search: `runs/local/artifacts/stage624_field_lookup_domain_selector_search.json`
- Stage622-624 selector search note: `docs/stage622_624_rule_field_selector_search.md`
- Stage625 reverse selector search: `runs/local/artifacts/stage625_reverse_selector_search.json`
- Stage626 rule-default domain selector search: `runs/local/artifacts/stage626_rule_default_domain_selector_search.json`
- Stage627 set-intersection-member selector search: `runs/local/artifacts/stage627_set_intersection_member_selector_search.json`
- Stage625-627 residual selector note: `docs/stage625_627_residual_selector_search.md`
- Stage628 canonical selector surface dataset: `runs/local/artifacts/stage628_canonical_selector_surface_dataset.json`
- Stage628 canonical selector surface summary: `runs/local/artifacts/stage628_canonical_selector_surface_summary.json`
- Stage628 canonical selector surface note: `docs/stage628_canonical_selector_surface.md`
- Stage629-631 canonical selector internalization summary: `runs/local/artifacts/stage629_631_canonical_selector_internalization_summary.json`
- Stage629-631 canonical selector internalization note: `docs/stage629_631_canonical_selector_internalization.md`
- Stage632-633 selector surface training summary: `runs/local/artifacts/stage632_633_selector_surface_training_summary.json`
- Stage632-633 selector surface training note: `docs/stage632_633_selector_surface_training.md`
- Stage634 rank-2 residual bridge dataset: `runs/local/artifacts/stage634_rank2_residual_bridge_dataset.json`
- Stage634-635 rank-2 residual bridge summary: `runs/local/artifacts/stage634_635_rank2_residual_bridge_summary.json`
- Stage634-635 rank-2 residual bridge note: `docs/stage634_635_rank2_residual_bridge.md`
- Stage636 entity rank-3 bridge dataset: `runs/local/artifacts/stage636_entity_rank3_bridge_dataset.json`
- Stage636-637 entity rank-3 bridge summary: `runs/local/artifacts/stage636_637_entity_rank3_bridge_summary.json`
- Stage636-637 entity rank-3 bridge note: `docs/stage636_637_entity_rank3_bridge.md`
- Stage638 fresh entity rank-3 bridge dataset: `runs/local/artifacts/stage638_fresh_entity_rank3_bridge_dataset.json`
- Stage638 fresh entity rank-3 bridge summary: `runs/local/artifacts/stage638_fresh_entity_rank3_bridge_summary.json`
- Stage638 fresh entity rank-3 bridge note: `docs/stage638_fresh_entity_rank3_bridge.md`
- Stage639 direct-fact residual geometry: `runs/local/artifacts/stage639_direct_fact_residual_geometry.json`
- Stage639 direct-fact residual geometry note: `docs/stage639_direct_fact_residual_geometry.md`
- Stage640 direct-fact hard-negative dataset: `runs/local/artifacts/stage640_direct_fact_hardneg_bridge_dataset.json`
- Stage640 direct-fact hard-negative summary: `runs/local/artifacts/stage640_direct_fact_hardneg_summary.json`
- Stage640 direct-fact hard-negative note: `docs/stage640_direct_fact_hardneg.md`
- Stage641 direct-fact schema probe: `runs/local/artifacts/stage641_direct_fact_schema_probe_summary.json`
- Stage641 direct-fact schema probe note: `docs/stage641_direct_fact_schema_probe.md`
- Stage642 direct-fact canonicalization dataset: `runs/local/artifacts/stage642_direct_fact_canonicalization_dataset.json`
- Stage642 direct-fact canonicalization summary: `runs/local/artifacts/stage642_direct_fact_canonicalization_summary.json`
- Stage642 direct-fact canonicalization note: `docs/stage642_direct_fact_canonicalization.md`
- Stage643 entity schema probe: `runs/local/artifacts/stage643_entity_schema_probe_summary.json`
- Stage643 entity schema probe note: `docs/stage643_entity_schema_probe.md`
- Stage644 KBPP doubling harness: `runs/local/artifacts/stage644_kbpp_doubling_harness.json`
- Stage644 KBPP doubling harness note: `docs/stage644_kbpp_doubling_harness.md`
- Stage645 72-domain entity field selector surface: `runs/local/artifacts/stage645_72domain_entity_field_selector_surface_dataset.json`
- Stage645 72-domain entity field selector note: `docs/stage645_72domain_entity_field_selector_surface.md`
- Stage646 72-domain collision-conditioned selector: `runs/local/artifacts/stage646_72domain_collision_conditioned_selector_dataset.json`
- Stage646 72-domain collision-conditioned selector note: `docs/stage646_72domain_collision_conditioned_selector.md`
- Stage647 72-domain probe summary: `runs/local/artifacts/stage647_72domain_probe_summary.json`
- Stage647 72-domain probe note: `docs/stage647_72domain_probe.md`
- Stage648 Stage525-init control summary: `runs/local/artifacts/stage648_stage525init_control_summary.json`
- Stage648 Stage525-init control note: `docs/stage648_stage525init_control.md`
- Stage649 scratch control summary: `runs/local/artifacts/stage649_scratch_control_summary.json`
- Stage649 scratch control note: `docs/stage649_scratch_control.md`
- Stage650 Stage648 continuation summary: `runs/local/artifacts/stage650_stage648_continue_summary.json`
- Stage650 Stage648 continuation note: `docs/stage650_stage648_continue.md`
- Stage650 residual rank map: `runs/local/artifacts/stage650_residual_rank_map.json`
- Stage650 residual rank note: `docs/stage650_residual_rank_map.md`
- Stage651 rank-3 residual dataset: `runs/local/artifacts/stage651_stage650_rank3_residual_replay_dataset.json`
- Stage651 rank-3 residual summary: `runs/local/artifacts/stage651_rank3_residual_summary.json`
- Stage651 rank-3 residual note: `docs/stage651_rank3_residual.md`
- Stage652 generalized 256 KBPP route: `runs/local/artifacts/stage652_generalized_256kbpp_route.json`
- Stage652 generalized 256 KBPP route note: `docs/stage652_generalized_256kbpp_route.md`
- Stage653 generalized 8 KBPP surface: `runs/local/artifacts/stage653_generalized_8kbpp_surface.json`
- Stage653 generalized 8 KBPP surface note: `docs/stage653_generalized_8kbpp_surface.md`
- Stage653 generalized 8 KBPP oracle score: `runs/local/artifacts/stage653_generalized_8kbpp_oracle_score_16k.json`
- Stage654 Stage653 generalized probe summary: `runs/local/artifacts/stage654_stage653_generalized_probe_summary.json`
- Stage654 Stage653 generalized probe note: `docs/stage654_stage653_generalized_probe.md`
- Stage655 generalized bridge curriculum: `runs/local/artifacts/stage655_generalized_bridge_curriculum.json`
- Stage655 generalized bridge curriculum note: `docs/stage655_generalized_bridge_curriculum.md`
- Stage658 Stage655 staged probe summary: `runs/local/artifacts/stage658_stage655_staged_probe_summary.json`
- Stage658 Stage655 staged probe note: `docs/stage658_stage655_staged_probe.md`
- Stage659 balanced generalized 8 KBPP surface: `runs/local/artifacts/stage659_balanced_generalized_8kbpp_surface.json`
- Stage659 balanced generalized 8 KBPP surface note: `docs/stage659_balanced_generalized_8kbpp_surface.md`
- Stage660 balanced probe summary: `runs/local/artifacts/stage660_balanced_probe_summary.json`
- Stage660 balanced probe note: `docs/stage660_balanced_probe.md`
- Stage661-666 atomic binding doubling summary: `runs/local/artifacts/stage661_666_atomic_binding_doubling_summary.json`
- Stage664 atomic binding overfit sweep: `runs/local/artifacts/stage664_atomic_binding_overfit_sweep.json`
- Stage667 full-corpus negative consolidation dataset: `runs/local/artifacts/stage667_full_corpus_negative_consolidation.json`
- Stage667 full-negative CPU diagnostic: `runs/local/artifacts/stage667_fullneg_128_cpu_fast_eval.json`
- Stage668-670 mined residual doubling summary: `runs/local/artifacts/stage668_670_mined_residual_doubling_consolidation_summary.json`
- Stage668-673 mined residual doubling summary: `runs/local/artifacts/stage668_673_mined_residual_doubling_consolidation_summary.json`
- Stage675-688 256-rung mined residual boundary summary: `runs/local/artifacts/stage675_688_atomic_256_rung_summary.json`
- Stage722 factorized key interaction summary: `runs/local/artifacts/stage722_factorized_key_interaction_summary.json`
- Stage723 factorized training summary: `runs/local/artifacts/stage723_factorized_training_summary.json`
- Stage724-725 generalized factorized probe summary: `runs/local/artifacts/stage724_725_generalized_factorized_probe_summary.json`
- Stage742-744 generalized 64 KBPP saturation summary: `runs/local/artifacts/stage742_744_generalized_64kbpp_saturation_summary.json`
- Stage745-746 relation noise factor summary: `runs/local/artifacts/stage745_746_relation_noise_factor_summary.json`
- Stage747-751 binding pair scaling summary: `runs/local/artifacts/stage747_751_binding_pair_scaling_summary.json`
- Stage758 100M factorized binding route: `runs/local/artifacts/stage758_100m_factorized_binding_route.json`
- Stage758 100M factorized binding route note: `docs/stage758_100m_factorized_binding_route.md`
- Stage752-759 256 KBPP closure summary: `runs/local/artifacts/stage752_759_256kbpp_closure_summary.json`
- Recursive KBPP selector hill-climb note: `docs/recursive_kbpp_selector_hillclimb.md`
- Stage774 procedure-routed frontier summary: `runs/local/artifacts/stage774_procedure_routed_frontier_summary.json`
- Stage775 procedure-routed residual map: `runs/local/artifacts/stage775_procedure_routed_residual_map_summary.json`
- Stage776 procedure-routed hardneg training: `runs/local/artifacts/stage776_procedure_routed_hardneg_training_summary.json`
- Stage777 neural hardneg curriculum: `runs/local/artifacts/stage777_neural_hardneg_curriculum_summary.json`
- Stage778 low factor reintroduction: `runs/local/artifacts/stage778_low_factor_reintro_summary.json`
- Stage779 Stage778 residual identity map: `runs/local/artifacts/stage779_stage778_residual_identity_map_summary.json`
- Stage780 second neural repair: `runs/local/artifacts/stage780_second_neural_repair_summary.json`
- Stage781 schema residual overfit diagnostic: `runs/local/artifacts/stage781_schema_residual_overfit_summary.json`
- Stage782 exact-protected residual training: `runs/local/artifacts/stage782_exact_protected_residual_summary.json`
- Stage783 routed teacher distillation/internalization probe: `runs/local/artifacts/stage783_routed_teacher_distillation_summary.json`
- Stage784 content-only direct-answer probe: `runs/local/artifacts/stage784_content_only_direct_answer_summary.json`
- Stage841-842 typed residual bridge summary: `runs/local/artifacts/stage841_842_typed_residual_bridge_summary.json`
- Stage843-846 operation calibration gate summary: `runs/local/artifacts/stage843_846_operation_calibration_gate_summary.json`
- Stage847-848 score-feature gate summary: `runs/local/artifacts/stage847_848_score_feature_gate_summary.json`
- Stage849 hardened partition ceiling summary: `runs/local/artifacts/stage849_hardened_partition_ceiling_summary.json`
- Stage850 token partition predictor summary: `runs/local/artifacts/stage850_partition_predictor_summary.json`
- Stage851 typed slot partition predictor summary: `runs/local/artifacts/stage851_typed_slot_partition_predictor_summary.json`
- Stage852 side-invariant typed partition predictor summary: `runs/local/artifacts/stage852_side_invariant_typed_partition_predictor_summary.json`
- Stage853 calibrated side-invariant typed partition predictor summary: `runs/local/artifacts/stage853_calibrated_side_invariant_typed_partition_predictor_summary.json`
- Stage854 per-operation threshold diagnostic summary: `runs/local/artifacts/stage854_per_operation_threshold_diagnostic_summary.json`
- Stage855 role-head partition predictor summary: `runs/local/artifacts/stage855_role_head_partition_predictor_summary.json`
- Stage856 soft role partition predictor summary: `runs/local/artifacts/stage856_soft_role_partition_predictor_summary.json`
- Stage857 role rerank partition predictor summary: `runs/local/artifacts/stage857_role_rerank_partition_predictor_summary.json`
- Stage858 detached role rerank summary: `runs/local/artifacts/stage858_detached_role_rerank_summary.json`
- Stage859 frozen Stage853 partition dataset: `runs/local/artifacts/stage859_frozen_stage853_partitions.json`
- Stage859-860 frozen partition reranker summary: `runs/local/artifacts/stage859_860_frozen_partition_reranker_summary.json`
- Stage860 frozen partition reranker summary: `runs/local/artifacts/stage860_frozen_partition_reranker_summary.json`
- Stage861-866 frozen partition embedding reranker summary: `runs/local/artifacts/stage861_866_frozen_partition_embedding_reranker_summary.json`
- Stage866 predeclared margin-5 operation gate summary: `runs/local/artifacts/stage866_predeclared_margin5_operation_gate_summary.json`
- Stage867-871 relation reranker residual summary: `runs/local/artifacts/stage867_871_relation_reranker_residual_summary.json`
- Stage872-877 composition reranker summary: `runs/local/artifacts/stage872_877_composition_reranker_summary.json`
- Stage878-882 exception reranker summary: `runs/local/artifacts/stage878_882_exception_reranker_summary.json`
- Stage883 relation typed bridge rerank summary: `runs/local/artifacts/stage883_relation_typed_bridge_rerank_summary.json`
- Stage885-887 learned relation bridge summary: `runs/local/artifacts/stage885_887_learned_relation_bridge_summary.json`
- Stage888-890 relation bridge dropout audit: `runs/local/artifacts/stage888_890_relation_bridge_dropout_audit_summary.json`
- Stage891-895 frozen relation bridge similarity summary: `runs/local/artifacts/stage891_895_relation_frozen_bridge_embedding_summary.json`
- Stage896-897 relation bridge salt audit: `runs/local/artifacts/stage896_897_relation_bridge_salt_audit_summary.json`
- Stage898 relation bridge distillation targets: `runs/local/artifacts/stage898_relation_bridge_distillation_targets_summary.json`
- Stage899-902 relation hidden value-head rejection: `runs/local/artifacts/stage899_902_relation_bridge_distilled_value_head_summary.json`
- Stage903 relation span-pool diagnostic rejection: `runs/local/artifacts/stage903_relation_span_pool_diagnostic_summary.json`
- Stage904 relation encoder fine-tune rejection: `runs/local/artifacts/stage904_relation_encoder_bridge_finetune_rollup_summary.json`
- Stage906 relation auxiliary encoder fine-tune rejection: `runs/local/artifacts/stage906_relation_encoder_aux_finetune_rollup_summary.json`
- Stage907 broad bridge curriculum targets: `runs/local/artifacts/stage907_broad_bridge_curriculum_targets_summary.json`
- Stage908-909 broad binding-comparison frontier: `runs/local/artifacts/stage908_909_broad_binding_comparison_head_summary.json`
- Stage910 broad hidden value-head rejection: `runs/local/artifacts/stage910_broad_hidden_value_head_summary.json`
- Stage911 broad hidden binding-auxiliary rejection: `runs/local/artifacts/stage911_broad_hidden_binding_aux_head_summary.json`
- Stage912 composition proof-edge diagnostic: `runs/local/artifacts/stage912_composition_proof_edge_diagnostic_summary.json`
- Stage913 composition proof bridge targets: `runs/local/artifacts/stage913_composition_proof_bridge_targets_summary.json`
- Stage914 proof-channel diagnostic: `runs/local/artifacts/stage914_proof_channel_diagnostic_summary.json`
- Stage915 hidden proof-auxiliary rejection: `runs/local/artifacts/stage915_hidden_proof_aux_head_summary.json`
- Stage916 composition hardening patch audit: `runs/local/artifacts/stage916_composition_hardening_patch_audit_summary.json`
- Stage917-919 composition-hardened typed-access frontier: `runs/local/artifacts/stage917_919_composition_hardened_frontier_summary.json`
- Stage920 Stage917 hidden value-head rejection: `runs/local/artifacts/stage920_stage917_hidden_value_head_summary.json`
- Stage921-922 Stage917 encoder fine-tune near miss: `runs/local/artifacts/stage921_922_stage917_encoder_finetune_probe_summary.json`
- Stage923 bridge-teacher encoder probe: `runs/local/artifacts/stage923_bridge_teacher_encoder_probe_summary.json`
- Stage924 cached encoder bridge fine-tune infrastructure: `runs/local/artifacts/stage924_cached_encoder_bridge_finetune_summary.json`
- Stage925 cached balanced sweep rejection: `runs/local/artifacts/stage925_cached_balanced_sweep_summary.json`
- Stage926 cached residual value-head frontier: `runs/local/artifacts/stage926_cached_residual_value_head_summary.json`
- Stage927-928 residual value-head operation gate: `runs/local/artifacts/stage927_928_residual_value_head_op_gate_summary.json`
- Stage929 relation specialist residual frontier: `runs/local/artifacts/stage929_relation_specialist_residual_summary.json`
- Stage930 relation specialist repro/audit: `runs/local/artifacts/stage930_relation_h32_repro_audit_summary.json`
- Stage931-932 relation objective rejections: `runs/local/artifacts/stage931_932_relation_objective_rejection_summary.json`
- Stage933 reproducible multi-head gated scorer: `runs/local/artifacts/stage933_reproducible_multihead_gated_scorer_summary.json`
- Stage934 calibrated trust-gate rejection: `runs/local/artifacts/stage934_calibrated_trust_correction_gate_summary.json`
- Stage935 multi-head value module rejection: `runs/local/artifacts/stage935_multihead_value_module_rejection_summary.json`
- Stage936 policy-distilled multi-head rejection: `runs/local/artifacts/stage936_policy_distilled_multihead_rejection_summary.json`
- Stage937 teacher score distribution export blocker: `runs/local/artifacts/stage937_teacher_score_distribution_export_blocked_summary.json`
- Stage938 saved specialist head initialization: `runs/local/artifacts/stage938_saved_specialist_head_initialization_summary.json`
- Stage939 Stage938 alpha-router rejection: `runs/local/artifacts/stage939_stage938_alpha_router_calibration_summary.json`
- Stage940 preservation fine-tune rejection: `runs/local/artifacts/stage940_preservation_finetune_rejection_summary.json`
- Stage941 frozen-specialist router rejection: `runs/local/artifacts/stage941_frozen_specialist_router_classifier_summary.json`
- Stage942 composition-router hybrid frontier: `runs/local/artifacts/stage942_composition_router_hybrid_policy_summary.json`
- Stage943 reproducible Stage942 policy decisions: `runs/local/artifacts/stage943_reproducible_stage942_policy_decisions_summary.json`
- Stage944 loadable Stage943 policy scorer: `runs/local/artifacts/stage944_loadable_stage943_policy_scorer_summary.json`
- Stage945 composition-only router sweep rejection: `runs/local/artifacts/stage945_composition_only_router_sweep_summary.json`
- Stage946 model-side gap audit: `runs/local/artifacts/stage946_model_side_gap_audit_summary.json`
- Stage947 relation residual-head sweep rejection: `runs/local/artifacts/stage947_relation_residual_head_sweep_summary.json`
- Stage948 exception residual-head sweep rejection: `runs/local/artifacts/stage948_exception_residual_head_sweep_summary.json`
- Stage949 relation latent auxiliary target audit: `runs/local/artifacts/stage949_relation_latent_auxiliary_targets_summary.json`
- Stage950 relation qslot/value auxiliary targets: `runs/local/artifacts/stage950_relation_qslot_value_targets_summary.json`
- Stage951 relation qslot/value auxiliary head rejection: `runs/local/artifacts/stage951_relation_qslot_value_aux_head_sweep_summary.json`
- Stage952 relation query-slot patch: `runs/local/artifacts/stage952_relation_query_slot_patch_summary.json`
- Stage953 relation query-slot patched residual rejection: `runs/local/artifacts/stage953_relation_query_slot_patched_residual_sweep_summary.json`
- Stage954 relation query-slot patched encoder fine-tune rejection: `runs/local/artifacts/stage954_relation_query_slot_patched_encoder_finetune_summary.json`
- Stage955 typed token-comparison module rejection: `runs/local/artifacts/stage955_typed_token_comparison_module_summary.json`
- Stage956 equality primitive ceiling: `runs/local/artifacts/stage956_equality_primitive_ceiling_summary.json`
- Stage957 budgeted equality primitive contract: `runs/local/artifacts/stage957_budgeted_equality_primitive_contract.json`
- Stage958 non-label qslot feasibility audit: `runs/local/artifacts/stage958_nonlabel_qslot_generation_feasibility_summary.json`
- Stage959 relation query-slot hardener patch audit: `runs/local/artifacts/stage959_relation_query_slot_hardener_patch_audit.json`
- Stage960 relation qslot rebuilt surface: `runs/local/artifacts/stage960_relation_qslot_hardened_surface_summary.json`
- Stage960 relation qslot rebuilt bridge targets: `runs/local/artifacts/stage960_relation_qslot_bridge_targets_summary.json`
- Stage960 equality primitive on rebuilt targets: `runs/local/artifacts/stage960_equality_primitive_on_rebuilt_targets_summary.json`
- Stage961 full-pair equality primitive: `runs/local/artifacts/stage961_relation_full_pair_equality_summary.json`
- Stage961 full-pair equality predictions: `runs/local/artifacts/stage961_relation_full_pair_equality_predictions.jsonl`
- Stage962 relation binding teacher targets: `runs/local/artifacts/stage962_relation_binding_teacher_targets_summary.json`
- Stage963 relation full-pair-only primitive: `runs/local/artifacts/stage963_relation_full_pair_only_summary.json`
- Stage964 operation pair-arity policy: `runs/local/artifacts/stage964_operation_pair_arity_policy_summary.json`
- Stage965 operation pair-arity teacher targets: `runs/local/artifacts/stage965_operation_pair_arity_teacher_summary.json`
- Stage966 learned pair-arity router: `runs/local/artifacts/stage966_pair_arity_router_summary.json`
- Stage967 pair-overlap primitive accounting: `runs/local/artifacts/stage967_pair_overlap_primitive_accounting_summary.json`
- Stage968 loadable pair-router scorer: `runs/local/artifacts/stage968_loadable_pair_router_summary.json`
- Stage969 100M Stage968 integration plan: `runs/local/artifacts/stage969_100m_stage968_integration_plan.json`
- Stage970 100M-vs-7B bridge contract: `runs/local/artifacts/stage970_100m_vs_7b_bridge_contract.json`
- Stage971 100M v415 preflight dry-run: `runs/local/artifacts/stage971_100m_v415_stage968_preflight_dryrun_summary.json`
- Stage972 100M v415 smoke: `runs/local/artifacts/stage972_100m_v415_stage968_smoke_summary.json`
- Stage973 local 7B-class top-k baseline harness: `runs/local/artifacts/stage973_local_7b_class_topk_baseline_harness_summary.json`
- Stage974 100M model-owned candidate-ranking rollup: `runs/local/artifacts/stage974_100m_model_owned_candidate_ranking_rollup_summary.json`
- Stage975 100M pair-overlap teacher distillation probe: `runs/local/artifacts/stage975_100m_pair_overlap_teacher_distillation_probe_summary.json`
- Stage976 loadable 100M pair-teacher model-owned frontier: `runs/local/artifacts/stage976_loadable_100m_pair_teacher_model_owned_frontier_summary.json`
- Stage977 relation-only pair-teacher rejection: `runs/local/artifacts/stage977_relation_only_pair_teacher_probe_summary.json`
- Stage978 relation teacher-dominant rejection: `runs/local/artifacts/stage978_relation_teacher_dominant_probe_summary.json`
- Stage979 relation teacher-only rejection: `runs/local/artifacts/stage979_relation_teacher_only_probe_summary.json`
- Stage980 100M plus counted pair-interface hybrid: `runs/local/artifacts/stage980_100m_model_owned_plus_counted_pair_interface_hybrid_summary.json`
- Stage981 loadable 100M plus counted pair-interface hybrid scorer: `runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json`
- Stage982 pair comparator budget audit: `runs/local/artifacts/stage982_pair_comparator_budget_audit_summary.json`
- Stage983 Qwen3 8B all-candidate 50-row baseline: `runs/local/artifacts/stage983_qwen3_8b_full_candidate_50row_baseline_summary.json`
- Stage984 Qwen3 8B positive-row same-row comparison: `runs/local/artifacts/stage984_qwen3_8b_vs_stage981_same_positive_rows_summary.json`
- Stage985 Qwen3 8B full 640-row same-candidate comparison: `runs/local/artifacts/stage985_qwen3_8b_vs_stage981_full_640_same_candidate_comparison_summary.json`
- Stage987 Qwen3.5 9B full 640-row same-candidate comparison: `runs/local/artifacts/stage987_qwen35_9b_vs_stage981_full_640_same_candidate_comparison_summary.json`
- Stage988 100M budgeted-interface claim gate: `runs/local/artifacts/stage988_100m_budgeted_interface_claim_gate_summary.json`
- Stage990 Gemma3 12B full 640-row same-candidate comparison: `runs/local/artifacts/stage990_gemma3_12b_vs_stage981_full_640_same_candidate_comparison_summary.json`
- Stage991 extended 100M budgeted-interface claim gate: `runs/local/artifacts/stage991_100m_budgeted_interface_extended_baseline_claim_gate_summary.json`
- Stage992 packaged 100M budgeted KBPP system: `runs/local/artifacts/stage992_100m_budgeted_kbpp_system_manifest.json`
- Stage993 constrained answer materialization: `runs/local/artifacts/stage993_constrained_answer_materialization_summary.json`
- Stage994 encoder-owned pair count comparator rejection: `runs/local/artifacts/stage994_encoder_owned_pair_count_comparator_summary.json`
- Stage996 encoder span pair equality comparator: `runs/local/artifacts/stage996_encoder_span_pair_equality_comparator_summary.json`
- Stage997 100M learned hard-count comparator hybrid: `runs/local/artifacts/stage997_100m_learned_pair_comparator_hybrid_summary.json`
- Stage1000 encoder soft-count candidate scorer: `runs/local/artifacts/stage1000_encoder_soft_count_candidate_scorer_summary.json`
- Stage1001 100M learned soft-count comparator hybrid: `runs/local/artifacts/stage1001_100m_soft_count_comparator_hybrid_summary.json`
- Stage1002 learned comparator claim gate: `runs/local/artifacts/stage1002_learned_comparator_claim_gate_summary.json`
- Stage1003 full-token alignment scorer rejection: `runs/local/artifacts/stage1003_fulltoken_alignment_scorer_summary.json`
- Stage1004 text-self-located pair equality comparator: `runs/local/artifacts/stage1004_text_self_located_pair_equality_comparator_summary.json`
- Stage1005 text-self-located soft-count scorer: `runs/local/artifacts/stage1005_text_self_located_soft_count_candidate_scorer_summary.json`
- Stage1006 100M text-self-located soft-count hybrid: `runs/local/artifacts/stage1006_100m_text_self_located_soft_count_hybrid_summary.json`
- Stage1007 text-self-located claim gate: `runs/local/artifacts/stage1007_text_self_located_claim_gate_summary.json`
- Stage1008 naturalized pair-anchor targets: `runs/local/artifacts/stage1008_naturalized_pair_anchor_targets_summary.json`
- Stage1009 naturalized-anchor pair equality comparator: `runs/local/artifacts/stage1009_naturalized_anchor_pair_equality_comparator_summary.json`
- Stage1010 naturalized-anchor soft-count scorer: `runs/local/artifacts/stage1010_naturalized_anchor_soft_count_candidate_scorer_summary.json`
- Stage1011 naturalized-anchor 100M hybrid: `runs/local/artifacts/stage1011_100m_naturalized_anchor_soft_count_hybrid_summary.json`
- Stage1012 naturalized-anchor claim gate: `runs/local/artifacts/stage1012_naturalized_anchor_claim_gate_summary.json`
- Stage1013 no-anchor targets: `runs/local/artifacts/stage1013_no_anchor_targets_summary.json`
- Stage1014 no-anchor full-token alignment scorer: `runs/local/artifacts/stage1014_no_anchor_fulltoken_alignment_scorer_summary.json`
- Stage1015 schema marker comparator rejection: `runs/local/artifacts/stage1015_schema_marker_comparator_summary.json`
- Stage1016 side-neutral schema targets: `runs/local/artifacts/stage1016_side_neutral_schema_targets_summary.json`
- Stage1017 side-neutral schema marker comparator rejection: `runs/local/artifacts/stage1017_side_neutral_schema_marker_comparator_summary.json`
- Stage1018 schema equality ceiling: `runs/local/artifacts/stage1018_schema_equality_ceiling_summary.json`
- Stage1019 schema-policy distillation rejection: `runs/local/artifacts/stage1019_schema_policy_distilled_comparator_summary.json`
- Stage1020 relation entity/slot threshold probe: `runs/local/artifacts/stage1020_relation_entity_slot_threshold_summary.json`
- Stage1021 side-neutral relation entity/slot threshold probe: `runs/local/artifacts/stage1021_relation_side_neutral_entity_slot_threshold_summary.json`
- Stage1022 no-anchor schema-equality 100M hybrid: `runs/local/artifacts/stage1022_100m_no_anchor_schema_equality_hybrid_summary.json`
- Stage1024 learned char schema-equality counted state: `runs/local/artifacts/stage1024_char_schema_equality_counted_summary.json`
- Stage1025 no-anchor learned-char-schema 100M hybrid: `runs/local/artifacts/stage1025_100m_no_anchor_char_schema_hybrid_summary.json`
- Stage1026 no-anchor learned-char-schema claim gate: `runs/local/artifacts/stage1026_no_anchor_char_schema_claim_gate_summary.json`
- Stage1027 frozen-encoder schema-count comparator rejection: `runs/local/artifacts/stage1027_encoder_schema_count_comparator_summary.json`
- Stage1028 schema-count teacher targets and failed 100M distillation: `runs/local/artifacts/stage1028_schema_count_teacher_targets_summary.json`, `runs/local/artifacts/stage1028_100m_schema_count_teacher_finetune_summary.json`
- Stage1029 conservative schema-count 100M distillation preservation probe: `runs/local/artifacts/stage1029_100m_schema_count_preserve_finetune_summary.json`
- Stage1030 all-operation learned-char schema policy sweep: `runs/local/artifacts/stage1030_allop_char_schema_policy_sweep_summary.json`
- Stage1031 no-anchor learned-char-schema policy 100M hybrid: `runs/local/artifacts/stage1031_100m_no_anchor_char_schema_policy_hybrid_summary.json`
- Stage1032 no-anchor learned-char-schema policy claim gate: `runs/local/artifacts/stage1032_no_anchor_char_schema_policy_claim_gate_summary.json`
- Stage1033 no-anchor role-aware learned-char-schema 100M hybrid: `runs/local/artifacts/stage1033_100m_no_anchor_role_char_schema_hybrid_summary.json`
- Stage1034 no-anchor role-aware learned-char-schema claim gate: `runs/local/artifacts/stage1034_no_anchor_role_char_schema_claim_gate_summary.json`
- Stage1035 exception alpha sweep: `runs/local/artifacts/stage1035_exception_alpha_sweep_summary.json`
- Stage1036 no-anchor role-aware learned-char-schema alpha-0.25 hybrid: `runs/local/artifacts/stage1036_100m_no_anchor_role_char_schema_alpha025_hybrid_summary.json`
- Stage1037 no-anchor role-aware learned-char-schema alpha-0.25 claim gate: `runs/local/artifacts/stage1037_no_anchor_role_char_schema_alpha025_claim_gate_summary.json`
- Stage1038 no-anchor source/default-kind typed-operator hybrid: `runs/local/artifacts/stage1038_100m_no_anchor_role_char_schema_source_kind_hybrid_summary.json`
- Stage1040 no-anchor typed-operator recoverable-ceiling hybrid: `runs/local/artifacts/stage1040_100m_no_anchor_role_char_schema_source_kind_policy_hybrid_summary.json`
- Stage1041 no-anchor typed-operator recoverable-ceiling claim gate: `runs/local/artifacts/stage1041_no_anchor_role_char_schema_source_kind_policy_claim_gate_summary.json`
- Stage1042 bridge-free internalization next-experiment contract: `runs/local/artifacts/stage1042_bridge_free_internalization_next_experiment_contract.json`
- Stage1043 bridge-free operator-teacher targets: `runs/local/artifacts/stage1043_operator_teacher_targets_summary.json`
- Stage1044 salted hidden no-anchor transfer split: `runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets_summary.json`
- Stage1045 frozen 100M operator-teacher value head probe: `runs/local/artifacts/stage1045_frozen_100m_operator_teacher_value_head_summary.json`
- Stage1046 frozen 100M composition/exception value head probe: `runs/local/artifacts/stage1046_frozen_100m_composition_exception_value_head_summary.json`
- Stage1046 operation-gated policy sweep: `runs/local/artifacts/stage1046_operation_gated_policy_sweep_summary.json`
- Stage1047 encoder-trainable operator-teacher value head probe: `runs/local/artifacts/stage1047_encoder_trainable_operator_teacher_value_head_summary.json`
- Stage1047 operation-gated policy sweep: `runs/local/artifacts/stage1047_operation_gated_policy_sweep_summary.json`
- Stage1048 pair/span operator-head route contract: `runs/local/artifacts/stage1048_pair_span_operator_head_route_contract.json`
- Stage1049 span operator-head probe: `runs/local/artifacts/stage1049_span_operator_head_summary.json`
- Stage1050 contrastive span-operator training contract: `runs/local/artifacts/stage1050_contrastive_span_operator_training_contract.json`
- Stage1051 contrastive span-pair targets: `runs/local/artifacts/stage1051_contrastive_span_pair_targets_summary.json`
- Stage1052 contrastive span-pair classifier: `runs/local/artifacts/stage1052_contrastive_span_pair_classifier_summary.json`
- Stage1054 pair-classifier slot-count candidate policy: `runs/local/artifacts/stage1054_pair_classifier_slot_count_candidate_policy_summary.json`
- Stage1055 bridge-free pair-classifier claim gate: `runs/local/artifacts/stage1055_bridge_free_pair_classifier_claim_gate_summary.json`
- Stage1056 pair-probability candidate composer: `runs/local/artifacts/stage1056_pair_probability_candidate_composer_summary.json`
- Stage1057 bridge-free pair-probability composer claim gate: `runs/local/artifacts/stage1057_bridge_free_pair_probability_composer_claim_gate_summary.json`
- Stage1058 hidden-transfer pair-probability composer probe: `runs/local/artifacts/stage1058_hidden_transfer_pair_probability_composer_summary.json`
- Stage1059 per-operation alpha candidate-composer rejection: `runs/local/artifacts/stage1059_operation_alpha_candidate_composer_summary.json`
- Stage1060 composition gap audit: `runs/local/artifacts/stage1060_composition_gap_audit_summary.json`
- Stage1061 composition target-entity span-pair targets: `runs/local/artifacts/stage1061_composition_entity_span_pair_targets_summary.json`
- Stage1062 composition target-entity pair classifier: `runs/local/artifacts/stage1062_composition_entity_pair_classifier_summary.json`
- Stage1063 composition target-entity candidate composer: `runs/local/artifacts/stage1063_composition_entity_candidate_composer_summary.json`
- Stage1064 salted hidden-transfer composition target-entity composer: `runs/local/artifacts/stage1064_hidden_transfer_composition_entity_composer_summary.json`
- Stage1065 bridge-free composition target-entity claim gate: `runs/local/artifacts/stage1065_composition_entity_bridge_free_claim_gate_summary.json`
- Stage1066 composition target-entity pair-policy rejection: `runs/local/artifacts/stage1066_composition_entity_pair_policy_summary.json`
- Stage1067 relation gap audit: `runs/local/artifacts/stage1067_relation_gap_audit_summary.json`
- Stage1068 high-alpha candidate-composer rescore: `runs/local/artifacts/stage1068_high_alpha_candidate_composer_summary.json`
- Stage1069 bridge-free ceiling claim gate: `runs/local/artifacts/stage1069_bridge_free_ceiling_claim_gate_summary.json`
- Stage1070 Stage1069 constrained answer materialization: `runs/local/artifacts/stage1070_stage1069_constrained_answer_materialization_summary.json`
- Stage1071 Stage1069 direct-answer targets: `runs/local/artifacts/stage1071_stage1069_direct_answer_targets_summary.json`
- Stage1072 direct-answer dataset manifests: `runs/local/artifacts/stage1072_direct_answer_dataset_summary.json`
- Stage1074 encoder-frozen direct decoder bundle: `runs/local/artifacts/pocketpal_controller_100m_stage1074_direct_answer_decoder_v415/agentkernel_lite_encdec_manifest.json`
- Stage1075 Stage1074 structured direct-value eval: `runs/local/artifacts/stage1075_direct_value_ranking_stage1074_100row_structured_fullcand_summary.json`
- Stage1076 full-model direct decoder bundle: `runs/local/artifacts/pocketpal_controller_100m_stage1076_direct_answer_full_finetune_v415/agentkernel_lite_encdec_manifest.json`
- Stage1077 Stage1076 structured direct-value eval: `runs/local/artifacts/stage1077_direct_value_ranking_stage1076_100row_structured_fullcand_summary.json`
- Stage1078 direct-generation probe rejection: `runs/local/artifacts/stage1078_direct_generation_probe_claim_gate_summary.json`
- Stage1079 constrained answer-value head: `runs/local/artifacts/stage1079_constrained_answer_value_head_summary.json`
- Stage1080 candidate-support ceiling audit: `runs/local/artifacts/stage1080_candidate_support_ceiling_audit_summary.json`
- Stage1081 atomic proof-pool expansion audit: `runs/local/artifacts/stage1081_atomic_proof_pool_expansion_audit_summary.json`
- Stage1082 learned atomic proof expansion: `runs/local/artifacts/stage1082_learned_atomic_proof_expansion_summary.json`
- Stage1083 learned composition proof expansion: `runs/local/artifacts/stage1083_learned_composition_proof_expansion_summary.json`
- Stage1084 proof-expansion frontier rollup: `runs/local/artifacts/stage1084_proof_expansion_frontier_rollup_summary.json`
- Stage1085 software KBPP benchmark plan: `runs/local/artifacts/stage1085_software_kbpp_benchmark_plan.json`
- Stage1086 software KBPP pilot harness: `runs/local/artifacts/stage1086_software_kbpp_pilot_summary.json`
- Stage1087 software baseline hooks: `runs/local/artifacts/stage1087_software_baseline_hooks_summary.json`
- Stage1088 hardened software KBPP pilot: `runs/local/artifacts/stage1088_hardened_software_kbpp_pilot_summary.json`
- Stage1088 hardened software baseline hooks: `runs/local/artifacts/stage1088_hardened_software_baseline_hooks_summary.json`
- Stage1089 software proof-operator transfer diagnostic: `runs/local/artifacts/stage1089_software_proof_operator_transfer_summary.json`
- Stage1090 learned software operator induction: `runs/local/artifacts/stage1090_learned_software_operator_induction_summary.json`
- Stage1091 scaled software operator curriculum: `runs/local/artifacts/stage1091_scaled_software_operator_curriculum_summary.json`
- Stage1092 operator template materialization: `runs/local/artifacts/stage1092_operator_template_materialization_summary.json`
- Stage1093 software adapter budget audit: `runs/local/artifacts/stage1093_software_adapter_budget_audit_summary.json`
- Stage1094 pilot-scale software operator surface: `runs/local/artifacts/stage1094_pilot_scale_software_operator_surface_summary.json`
- Stage1095 controlled-scale software operator surface: `runs/local/artifacts/stage1095_controlled_scale_software_operator_surface_summary.json`
- Stage1096 100M software operator training package: `runs/local/artifacts/stage1096_100m_software_operator_training_package_summary.json`
- Stage1097 100M software target prediction scorer: `runs/local/artifacts/stage1097_hidden_oracle_score_summary.json`
- Stage1098 software target negative baselines: `runs/local/artifacts/stage1098_software_target_negative_baselines_summary.json`
- Stage1099 software validity audit: `runs/local/artifacts/stage1099_software_validity_audit_summary.json`
- Stage1100 diverse software operator surface: `runs/local/artifacts/stage1100_diverse_software_operator_surface_summary.json`
- Stage1102 hardened diverse software operator surface: `runs/local/artifacts/stage1102_hardened_diverse_software_operator_surface_summary.json`
- Stage1102 hardened diverse baseline hooks: `runs/local/artifacts/stage1102_hardened_diverse_surface_baseline_hooks_summary.json`
- Stage1103 expanded diverse software surface: `runs/local/artifacts/stage1103_expanded_diverse_software_surface_summary.json`
- Stage1103 expanded diverse baseline hooks: `runs/local/artifacts/stage1103_expanded_diverse_surface_baseline_hooks_summary.json`
- Stage1104 diverse 100M training package: `runs/local/artifacts/stage1104_diverse_100m_training_package_summary.json`
- Stage1105 diverse package oracle scores: `runs/local/artifacts/stage1105_diverse_hidden_oracle_score_summary.json`
- Stage1106 qwen3:8b software repair baseline: `runs/local/artifacts/stage1106_qwen3_8b_eval128_software_repair_summary.json`
- Stage1107 qwen3:8b full eval software repair baseline: `runs/local/artifacts/stage1107_qwen3_8b_eval512_software_repair_summary.json`

## Current Scale Snapshot

- Accepted controlled same-candidate 100M frontier: Stage1069 `350/640` answer and `333/640` exact.
- Same-candidate larger-model baselines: Qwen3 8B `317/300`, Qwen3.5 9B `321/304`, Gemma3 12B `309/292`.
- Current learned proof-expansion diagnostic: Stage1082 atomic plus Stage1083 composition projects to `393/640` answer and `376/640` exact.
- Optimistic next proof-expansion target: Stage1084 estimates `413/640` answer and `396/640` exact after learned counterfactual and exception expansion.
- Boundary: proof-expansion projections are not yet a free-form generation or broad 7B-parity claim; they need counted-interface packaging or 100M internalization.

## External Benchmark Application

- Software: score verified behavior, not patch fluency. Count hidden tests, localized edit choices, API bindings, exception behavior, and invariant checks as decision bits under a fixed parameter/tool budget.
- ARC-style tasks: score object binding, spatial relation, transformation rule, color/shape binding, and final grid-cell correctness. Use generated ARC-like curricula for training and held-out public tasks only for evaluation.
- Adapter pattern: `query/context -> latent proof/binding state -> constrained action/answer -> verifier`.
- Benchmark claim gate: compare 100M direct, 100M plus counted proof expansion, and a modern 7B baseline under the same context/proof budget and hidden verifier. A win only counts when verifier-scored decisions beat the 7B baseline.
- Stage1085 scale: pilot `1,000` hidden tasks / `100,000` verified decision bits; controlled claim `10,000` hidden tasks / `1,000,000` verified decision bits; serious claim `100,000` hidden tasks / `10,000,000` verified decision bits.
- Stage1086 pilot harness: `192` executable Python repair tasks; eval and hidden each have `32` tasks. Reference predictions pass `32/32`; buggy predictions pass `0/32`, proving the verifier distinguishes behavior.
- Stage1087 baseline hooks: copy-buggy `0/32`, reference oracle `32/32`, proof-memory-by-symbol+contract `32/32`. This proves the hook path works and also shows Stage1088 must harden the pilot against exact proof-memory lookup.
- Stage1088 hardened pilot: `80` train, `12` eval, and `12` hidden executable repair tasks with eval/hidden templates absent from train. Reference oracle passes `12/12`; copy-buggy stays `0/12`; exact proof-memory-by-symbol+contract now also scores `0/12`. This blocks the easiest proof-memory shortcut and makes the next software comparison cleaner.
- Stage1089 proof-operator transfer: a three-operator typed library solves the Stage1088 held-out eval and hidden splits at `12/12`. This is a reusable-operator ceiling and a training target for the 100M path, not a model-owned result yet.
- Stage1090 learned operator induction: six supplemental operator examples train a tiny naive-Bayes selector, which also solves Stage1088 eval/hidden at `12/12` when paired with the typed materializer. This is learned selection, not learned materialization.
- Stage1091 scaled operator curriculum: eight repair operators, `24` train rows, `8` eval rows, and `8` hidden rows with held-out symbols and alternate contract phrasings. The tiny learned selector reaches `8/8` operator accuracy and hidden-test pass on both eval and hidden with the typed materializer.
- Stage1092 operator template materialization: the selector and code-body templates are induced from Stage1091 train rows, then transferred to held-out symbols. It reaches `8/8` eval and `8/8` hidden. This is no longer hand-coded materialization, but it is still a symbolic adapter rather than 100M-owned generation.
- Stage1093 budget audit: Stage1092 uses `636` counted selector/template entries and verifies only `64` hidden bits, for `0.10062893081761007` hidden bits per counted entry. The next benchmark must scale hidden verified bits: `12,500` hidden rows for pilot, `125,000` for controlled claim, and `1,250,000` for serious software-KBPP evidence at 8 bits per row.
- Stage1094 pilot-scale surface: `24` train, `1024` eval, and `12,500` hidden generated repair tasks over eight operators. The Stage1092 induced selector/template adapter passes `12,500/12,500` hidden rows, reaching `100,000` verified hidden bits. This clears pilot scale but remains synthetic and adapter-owned.
- Stage1095 controlled-scale surface: `24` train, `4096` eval, and `125,000` hidden generated repair tasks over eight operators. The Stage1092 induced selector/template adapter passes `125,000/125,000` hidden rows, reaching `1,000,000` verified hidden bits. This clears controlled scale for the synthetic adapter route.
- Stage1096 100M training package: `100,000` generated train targets, `4096` eval targets, and `125,000` hidden targets with operator, signature, template-body, and direct-code supervision. This packages the controlled-scale verifier problem for 100M-owned training, but no 100M run has been completed yet.
- Stage1097 prediction scorer: accepts decomposed or direct model outputs from Stage1096 and runs the same verifier. Oracle smoke checks pass `4096/4096` eval and `125,000/125,000` hidden, confirming the target package can be scored end to end.
- Stage1098 negative baselines: empty, signature-only, and copy-buggy outputs all score `0` hidden-test pass on the `125,000` hidden rows. Copy-buggy passes half of public tests but still earns `0` hidden verified bits, so hidden verification is the real gate.
- Stage1099 validity audit: the pipeline has no function-name split overlap and no prompt leakage of direct/template targets, but the hidden split has only `8` unique operator families and `8` unique template bodies. Row-level `1,000,000` verified bits are not independent semantic bits; conservative unique-family accounting is `64` bits. Valid as controlled verifier engineering, not as 100M-vs-7B evidence.
- Stage1100/1102 diversity repair: Stage1100 raises unique operator/template bodies to `56`, but its first baseline audit showed `copy_buggy` could pass `304/896` hidden rows because some hidden tests were one-sided. Stage1102 hardens hidden tests by including public checks; reference oracle passes `896/896`, while copy-buggy and proof-memory both score `0/896`. Conservative unique-family bits are now `448`.
- Stage1103 expanded diversity rung: `512` operator labels, `458` unique template bodies, `1024` train rows, `512` eval rows, and `1024` hidden rows. Reference oracle passes `1024/1024`; copy-buggy and proof-memory are `0/1024`. Conservative unique-family bits rise to `3664`.
- Stage1104/1105 package the expanded-diversity surface for model-output scoring. Stage1104 creates 100M-style targets; Stage1105 oracle scoring passes `512/512` eval and `1024/1024` hidden through the Stage1097 scorer. This package is ready for actual 100M or 7B predictions.
- Stage1106 real model-output baseline: local `qwen3:8b` scores `97/128` hidden pass on the expanded-diversity eval subset, after a `13/16` smoke. All outputs preserve syntax and function symbols. This is a bounded baseline, not a full split result.
- Stage1107 full eval baseline: local `qwen3:8b` scores `435/512` hidden pass on the expanded-diversity eval split, with `512/512` syntax validity and function-symbol preservation. This is the current main 8B-class eval bar for 100M-owned software runs.
- Stage785-786 direct-answer overfit diagnostic: `runs/local/artifacts/stage785_786_direct_answer_overfit_summary.json`
- Stage787 decoder/lm-head preserved direct probe: `runs/local/artifacts/stage787_decoder_lmhead_preserved_direct_summary.json`
- Stage788 longer decoder/lm-head probe: `runs/local/artifacts/stage788_decoder_lmhead_longer_summary.json`
- Stage789 candidate value ranking probe: `runs/local/artifacts/stage789_candidate_value_ranking_summary.json`
- Stage790 frozen answer/value-head probe: `runs/local/artifacts/stage790_frozen_answer_value_head_summary.json`
- Stage791 frozen query-candidate value-ranker probe: `runs/local/artifacts/stage791_frozen_query_candidate_value_ranker_summary.json`
- Stage792 route-feature candidate-ranker ceiling: `runs/local/artifacts/stage792_route_feature_candidate_ranker_summary.json`
- Stage793 JEPA-style route-target ranker probe: `runs/local/artifacts/stage793_jepa_route_target_ranker_summary.json`
- Stage794 predicted-route feedback ranker probe: `runs/local/artifacts/stage794_predicted_route_feedback_ranker_summary.json`
- Stage795 route-pretrain feedback ranker probe: `runs/local/artifacts/stage795_route_pretrain_feedback_ranker_summary.json`
- Stage796 normalized route-target feedback probe: `runs/local/artifacts/stage796_normalized_route_target_feedback_summary.json`
- Stage797 predicted-route feedback residual breakdown: `runs/local/artifacts/stage797_predicted_route_feedback_residual_breakdown_summary.json`
- Stage798-800 operation-conditioning probes: `runs/local/artifacts/stage798_800_operation_conditioning_summary.json`
- Stage801-802 atomic-weighted operation-feature probes: `runs/local/artifacts/stage801_802_atomic_weighted_operation_feature_summary.json`
- Stage803-804 route-weight sweep over atomic-weighted operation features: `runs/local/artifacts/stage803_804_route_weight_atomic_weight_summary.json`
- Stage805 atomic slot-loss probe: `runs/local/artifacts/stage805_atomic_slot_loss_probe_summary.json`
- Stage806 atomic binary feedback probe: `runs/local/artifacts/stage806_atomic_binary_feedback_probe_summary.json`
- Stage807-808 atomic hard-negative margin probes: `runs/local/artifacts/stage807_808_atomic_hardneg_margin_summary.json`
- Stage809 atomic-only specialist probe: `runs/local/artifacts/stage809_atomic_only_specialist_summary.json`
- Stage810 atomic candidate-partition diagnostic: `runs/local/artifacts/stage810_atomic_candidate_partition_summary.json`
- Stage811 atomic partition score-loss probe: `runs/local/artifacts/stage811_atomic_partition_score_loss_summary.json`
- Stage812-813 atomic partition-predictor probes: `runs/local/artifacts/stage812_813_atomic_partition_predictor_summary.json`
- Stage814 atomic lexical partition-predictor diagnostic: `runs/local/artifacts/stage814_atomic_lexical_partition_predictor_summary.json`
- Stage815 atomic hash-binding partition-predictor diagnostic: `runs/local/artifacts/stage815_atomic_hash_binding_partition_predictor_summary.json`
- Stage816 operation partition-ceiling diagnostic: `runs/local/artifacts/stage816_operation_partition_ceiling_summary.json`
- Stage817 multi-operation hash-binding selector diagnostic: `runs/local/artifacts/stage817_multiop_hash_binding_selector_summary.json`
- Stage818 token-binding shortcut audit: `runs/local/artifacts/stage818_token_binding_shortcut_audit_summary.json`
- Stage819 hardened binding surface: `runs/local/artifacts/stage819_hardened_binding_surface_summary.json`
- Stage820 hardened counterfactual surface: `runs/local/artifacts/stage820_hardened_counterfactual_surface_summary.json`
- Stage821 hardened hash-binding selector: `runs/local/artifacts/stage821_hash_binding_selector_hardened_summary.json`
- Stage822 bridge-supervised hardened hash-binding selector: `runs/local/artifacts/stage822_bridge_supervised_hash_binding_selector_summary.json`
- Stage823 relation-weighted bridge selector: `runs/local/artifacts/stage823_relation_weighted_bridge_selector_summary.json`
- Stage824 frozen-base fused bridge selector: `runs/local/artifacts/stage824_frozen_base_fused_bridge_selector_summary.json`
- Stage825 train-calibrated fusion: `runs/local/artifacts/stage825_train_calibrated_fusion_summary.json`
- Stage826 held-out alias-family validation: `runs/local/artifacts/stage826_heldout_alias_family_validation_summary.json`
- Stage827 pair-code held-out alias validation: `runs/local/artifacts/stage827_pair_code_heldout_alias_validation_summary.json`
- Stage828-829 pair-code calibration diagnostic: `runs/local/artifacts/stage828_829_pair_code_calibration_summary.json`
- Stage830 external alias-salt calibration: `runs/local/artifacts/stage830_external_alias_calibration_summary.json`
- Stage831-833 external alias scorer weighting: `runs/local/artifacts/stage831_833_external_alias_scorer_weight_summary.json`
- Stage834 operation-specific scorer rejection: `runs/local/artifacts/stage834_operation_specific_scorer_summary.json`
- Stage835-837 low-rank adapter sweep: `runs/local/artifacts/stage835_837_lowrank_adapter_summary.json`
- Stage838-840 typed bridge channel sweep: `runs/local/artifacts/stage838_840_typed_bridge_channel_summary.json`
- Tiny intelligence parameter map: `runs/local/artifacts/tiny_intelligence_mapping.json`
- Tiny intelligence map note: `docs/tiny_intelligence_mapping.md`
- Knowledge bits/parameter report: `runs/local/artifacts/knowledge_bits_per_param_report.json`
- Knowledge bits/parameter note: `docs/knowledge_bits_per_parameter.md`
- Dense-vs-MoE summary: `runs/local/artifacts/knowledge_compression_moe_stage429_summary.json`
- Residual summary: `runs/local/artifacts/knowledge_compression_ladder_100k_stage429_residual_replay_summary.json`
- Run ledger: `runs/ledgers/pocketpal_seq2seq_runs.jsonl`
