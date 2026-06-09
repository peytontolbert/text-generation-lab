# Stage628 Canonical Selector Surface

Artifact: `runs/local/artifacts/stage628_canonical_selector_surface_summary.json`

## Summary

Stage628 rebuilds the selector surface from the clean Stage602 field-level dataset instead of continuing to stack recursive selector markers. The goal was to test whether the final selector map alone is enough:

- `direct_fact`, `entity_context`, `rule_default`: `domain:entity:field`
- `reverse_lookup_set`: `domain:field:answer`
- `rule_case_intersection_count`: `domain:rule_field:case:filter_field:filter_answer`
- `rule_case_intersection_member`: `domain:rule_field:case:entity`
- `two_hop_owner_region`: `domain:entity:owner`

The builder guards against doc-only final answer leakage. The only doc-only key intentionally used is `owner` for `two_hop_owner_region`; `owner_region` is not used.

## Result

Schema-only evaluation against the Stage602 16k bundle:

- Manifest: `runs/local/tmp/pocketpal_stage628_canonical_selector_surface_seed461/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9525641025641025` / `0.9653846153846154`
- Exact/answer bits/param: `1.532409132890377` / `1.5530337510988612`
- Average train retrieval tokens per pair: `145.47232975541087`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `111`

Compared with Stage626:

- Answer bits/param falls from `1.5757208311281938` to `1.5530337510988612`.
- Exact bits/param falls from `1.5571586747405581` to `1.532409132890377`.
- Average train retrieval tokens per pair improves from `152.886811543199` to `145.47232975541087`.

## Decision

Rejected as a pure-neural KBPP frontier. The canonical surface is shorter, but the Stage602 checkpoint benefits from the accumulated selector history. In particular, removing the older field lookup markers hurts `entity_context` and `direct_fact`:

- `entity_context` answer drops to `0.8333333333333334` versus Stage626's `0.9201388888888888`.
- `direct_fact` answer drops to `0.9337539432176656` versus Stage626's `0.9589905362776026`.

The positive finding is token efficiency under deterministic access: with hard filtering, Stage628 keeps perfect exact/answer and raises hard-filter answer bits per training token to `0.0007402713750969981`. That means canonical selectors may still be a better fresh-training or distillation format, but they are not a schema-only replacement for the current Stage626 frontier.
