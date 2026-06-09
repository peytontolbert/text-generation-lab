# Stage622-624 Rule And Field Selector Search

## Summary

Stages622-624 continue the recursive selector route from the Stage621 family-specific selector surface.

- Stage622 targets `rule_case_intersection_count`.
- Stage623 targets `rule_case_intersection_member` on top of Stage622.
- Stage624 returns to the largest remaining answer losses, `entity_context` and `direct_fact`, and tests domain-qualified field selectors.

## Stage622

Best template: `{domain}:{rule_field}:{case}:{filter_field}:{filter_answer}`

- Artifact: `runs/local/artifacts/stage622_rule_count_selector_search.json`
- Manifest: `runs/local/tmp/recursive_kbpp_selector_stage622_rule_count_selector/domain_rule_field_case_filter_field_filter_ab74e254eb/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9534188034188035` / `0.9615384615384616`
- Exact/answer bits/param: `1.5337841074376093` / `1.546846365636316`
- Rule-case intersection count exact/answer: `0.9837837837837838` / `0.9945945945945946`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `109`

Finding: rule count retrieval wants the full rule/filter answer identity. Removing domain or filter answer reduces global density.

## Stage623

Best template: `{domain}:{rule_field}:{case}:{entity}`

- Artifact: `runs/local/artifacts/stage623_rule_member_selector_search.json`
- Manifest: `runs/local/tmp/recursive_kbpp_selector_stage623_rule_member_selector/domain_rule_field_case_entity_c5cd86491c/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.95` / `0.9632478632478633`
- Exact/answer bits/param: `1.5282842092486804` / `1.5495963147307807`
- Rule-case intersection member exact/answer: `0.925207756232687` / `0.9750692520775623`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `117`

Finding: Stage623 is answer-positive but exact-negative relative to Stage622. Long member selectors with both filter answer and entity damage exact retrieval; the best member answer selector is shorter and drops `filter_answer`.

## Stage624

Best templates: `{domain}:{entity}:{field}` and `{domain}:{field}:{entity}` tie.

- Artifact: `runs/local/artifacts/stage624_field_lookup_domain_selector_search.json`
- Accepted manifest: `runs/local/tmp/recursive_kbpp_selector_stage624_field_lookup_domain_selector/domain_entity_field_00fdde0fa6/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9653846153846154` / `0.9773504273504273`
- Exact/answer bits/param: `1.5530337510988612` / `1.5722833947601134`
- Direct-fact exact/answer: `0.9589905362776026` / `0.9589905362776026`
- Entity-context exact/answer: `0.9166666666666666` / `0.9201388888888888`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `81`

Finding: adding domain to the field lookup selector is the largest KBPP gain since the selector route began. The earlier `entity:field` marker was useful, but `domain:entity:field` is much stronger under collision because entities and fields are only locally meaningful inside a domain. `domain:field:entity` ties it, while placing field first or entity first without domain-leading order is weaker.

## Decision

Stage624 is the accepted current schema-only KBPP frontier. It is not a new trained checkpoint; it uses the Stage602 neural bundle and improves the retrieval surface by exposing compact, family-specific binding identities.
