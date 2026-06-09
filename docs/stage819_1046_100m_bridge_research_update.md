# Stage819-1046 100M Bridge Research Update

> Current-frontier note: this document is a focused Stage819-1046 snapshot. It has been superseded for current frontier status by [Full Research Timeline](full_research_timeline.md), which carries the chronology through Stage1083. As of that timeline, Stage1069 is the accepted bridge-free controlled-ranking ceiling, Stage1078 rejects direct decoder completion, and Stage1083 is the next proof-expansion route.

Last updated: 2026-06-06

This note documents the late-stage research artifacts after the earlier generalized KBPP/factorized-binding docs. It is deliberately claim-gated: the current evidence supports a 100M typed candidate-selection interface result, not a bridge-free free-form reasoning claim.

## Snapshot Claim Boundary

Accepted:

- On the 640-row KBPP same-candidate benchmark, the 100M system plus declared typed comparators and a 97-parameter operation router beats local Qwen3 8B, Qwen3.5 9B, and Gemma3 12B prompt baselines on the same candidate sets.
- Stage1040 reaches the current recoverable ceiling on the no-anchor typed-interface surface: `350/640` answer and `333/640` exact, with implied full-split `580` answer and `562` exact.
- The current best interface no longer uses deterministic suffix set intersection, bridge fields, or explicit pair-anchor tokens, but it still uses a declared learned string-comparator plus typed-operator interface.

Not accepted:

- A bridge-free 100M model-owned claim.
- Encoder-owned natural-language equality/internalized pair-overlap counting.
- Direct/free-form generation parity with larger local models.
- Broad general-knowledge parity beyond the fixed candidate-selection interface.

## Key Artifacts

| stage | artifact | answer/exact | status |
|---|---|---:|---|
| Stage981 | `runs/local/artifacts/stage981_100m_pair_interface_hybrid_summary.json` | `342/325` eval, implied `572/554` | Budgeted interface with fixed pair-overlap/count comparator; accepted only as typed-interface evidence. |
| Stage991 | `runs/local/artifacts/stage991_100m_budgeted_interface_extended_baseline_claim_gate_summary.json` | `342/325` eval | Passes same-candidate Qwen3 8B, Qwen3.5 9B, and Gemma3 12B baselines by `25/25`, `21/21`, and `33/33`. |
| Stage997 | `runs/local/artifacts/stage997_100m_learned_pair_comparator_hybrid_summary.json` | `336/319` eval, implied `566/548` | Learned encoder-span comparator removes suffix set intersection but still depends on qpair/dpair marker locations. |
| Stage1025 | `runs/local/artifacts/stage1025_100m_no_anchor_char_schema_hybrid_summary.json` | `334/317` eval, implied `564/546` | No-anchor learned character schema equality; declared comparator interface remains. |
| Stage1040/1041 | `runs/local/artifacts/stage1041_no_anchor_role_char_schema_source_kind_policy_claim_gate_summary.json` | `350/333` eval, implied `580/562` | Current frontier; reaches recoverable ceiling and beats Stage981 by `8/8`. |
| Stage1045 | `runs/local/artifacts/stage1045_frozen_100m_operator_teacher_value_head_summary.json` | `271/254` with calibration blend | Frozen value head improves over base on some slices but stays below Stage976 and external baselines. |
| Stage1046 | `runs/local/artifacts/stage1046_operation_gated_policy_sweep_summary.json` | `282/265` with calibration-selected blend | Matches Stage976 but remains below 8B/9B/12B baselines; bridge-free frozen-head route is insufficient. |

## Stage981-991 Budgeted Interface Result

Stage981 combines the 100M Stage976 loadable model-owned exception residual with the Stage968 counted pair-overlap/count interface for `composition` and `relation`, routed by the Stage966 97-parameter arity router. Eval improves from the base `237/220` answer/exact to `342/325`, with recoverable ceiling `350/333`.

Stage991 extends the claim gate against local prompt baselines on the same full 640-row candidate sets:

- Qwen3 8B: `317/300`
- Qwen3.5 9B: `321/304`
- Gemma3 12B: `309/292`
- Stage981 budgeted interface: `342/325`

The correct wording is: the 100M system plus a declared comparator interface beats these local same-candidate prompt baselines. The result does not prove the 100M encoder learned the pair-overlap/count operator internally.

## No-Anchor Typed-Interface Progress

Stages997-1025 progressively remove fragile bridge assumptions:

- Stage997 replaces deterministic suffix set intersection with a learned encoder-span equality/count comparator, but still uses qpair/dpair marker locations.
- Stage1025 moves to no-anchor character schema equality, removing deterministic suffix set intersection and explicit pair anchors while keeping a declared comparator.
- Stage1040 adds role-aware character schema policy and source-kind typed operators. Stage1041 claim gate reports `350/333`, exactly the current recoverable eval ceiling, with no bridge-field access and no explicit pair-anchor tokens.

Stage1041 is the best accepted late-stage typed-interface frontier. It exceeds Stage981 by `8/8` and beats the same-candidate prompt baselines by:

- Qwen3 8B: `33/33`
- Qwen3.5 9B: `29/29`
- Gemma3 12B: `41/41`

The key limitation remains explicit in the artifact: this is still a declared learned string-comparator plus typed-operator interface, not encoder-owned equality.

## Bridge-Free Internalization Probe

Stage1042 defines the next experiment contract: export operator teacher targets, build a salted hidden no-anchor split, and require a bridge-free Stage1013-style eval that beats Stage976 `282/265` and Qwen3 8B `317/300`, with target `>=350/333` and no external comparator.

Stages1045-1046 test frozen 100M value heads trained on Stage1043 operator teacher targets:

- Stage1045 all-operation frozen value head reaches only `240/223` raw eval and `271/254` with calibration-selected blend.
- Stage1046 composition/exception-focused frozen value head reaches `236/219` raw eval and `282/265` with calibration-selected blend.
- The Stage1046 calibrated sweep exactly matches Stage976 `282/265`, but remains below Qwen3 8B `317/300` and the Stage1040 typed-interface frontier.

Decision: frozen embeddings are close but insufficient. The next proof needs encoder-owned operator-head training on salted hidden/no-anchor data, not more post-hoc interface scoring.

## Next Work

1. Use `runs/local/artifacts/stage1043_operator_teacher_targets.jsonl` and `runs/local/artifacts/stage1044_salted_hidden_no_anchor_targets.jsonl` for the next bridge-free internalization run.
2. Train encoder-owned operator heads with candidate CE, operator-head BCE, same-collision margin, Stage1040 teacher KL, and no-regression rows.
3. Gate on no external char comparator, no bridge fields, no deterministic suffix set intersection, and no explicit pair anchors.
4. Report free-form generation separately; it is not required for the candidate-ranking claim.
