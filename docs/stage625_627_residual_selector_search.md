# Stage625-627 Residual Selector Search

## Summary

Stages625-627 continue from the Stage624 domain-qualified field lookup frontier.

- Stage625 targets `reverse_lookup_set`.
- Stage626 targets `rule_default`.
- Stage627 tests `set_intersection_member` and is rejected.

## Stage625

Best template: `{domain}:{field}:{answer}`

- Artifact: `runs/local/artifacts/stage625_reverse_selector_search.json`
- Manifest: `runs/local/tmp/recursive_kbpp_selector_stage625_reverse_selector/domain_field_answer_919a74fb2e/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9670940170940171` / `0.979059829059829`
- Exact/answer bits/param: `1.5557837001933257` / `1.5750333438545778`
- Reverse lookup exact/answer: `1.0` / `1.0`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `77`

Adding `count` ties the answer score but increases token cost, so the shorter selector is preferred.

## Stage626

Best templates: `{domain}:{entity}:{field}`, `{domain}:{field}:{entity}`, and `{entity}:{domain}:{field}` tie on answer. `{domain}:{entity}:{field}` is accepted for consistency with Stage624.

- Artifact: `runs/local/artifacts/stage626_rule_default_domain_selector_search.json`
- Manifest: `runs/local/tmp/recursive_kbpp_selector_stage626_rule_default_domain_selector/domain_entity_field_00fdde0fa6/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.967948717948718` / `0.9794871794871794`
- Exact/answer bits/param: `1.5571586747405581` / `1.5757208311281938`
- Rule-default exact/answer: `1.0` / `1.0`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `75`

## Stage627

Best tested template: `{domain}:{field_a}:{field_b}:{entity}`

- Artifact: `runs/local/artifacts/stage627_set_intersection_member_selector_search.json`
- Best exact/answer: `0.9645299145299145` / `0.9786324786324786`
- Best exact/answer bits/param: `1.551658776551629` / `1.5743458565809616`
- Hard-filter corrections: `83`

Decision: rejected. Every tested set-intersection-member selector is below Stage626, and several over-specified variants damage unrelated operations. This family is better left to the existing collision key/filter surface for now.

## Current Frontier

Stage626 is the current schema-only KBPP frontier:

- Answer bits/param: `1.5757208311281938`
- Exact bits/param: `1.5571586747405581`
- Answer top1: `0.9794871794871794`
- Hard-filter corrections: `75`

The current selector map is:

- Direct/entity field lookup: `domain:entity:field`
- Reverse lookup: `domain:field:answer`
- Rule default: `domain:entity:field`
- Rule count intersection: `domain:rule_field:case:filter_field:filter_answer`
- Rule-member answer density: `domain:rule_field:case:entity`
- Two-hop composition: `domain:entity:owner`

## Follow-up

Stage628 tests whether this map can be rebuilt canonically from the clean Stage602 rows without keeping the accumulated recursive selector markers. It is shorter but not a schema-only frontier: exact/answer falls to `0.9525641025641025` / `0.9653846153846154`, and answer bits/param falls to `1.5530337510988612`. See `docs/stage628_canonical_selector_surface.md`.
