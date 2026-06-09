# Stage619-621 Selector Transfer

## Summary

Stages619-621 extend the minimal selector route beyond entity/direct rows.

- Stage619 applies `{entity}:{field}` broadly to every operation where those keys are available.
- Stage620 confirms that excluding `two_hop_owner_region` changes nothing, because two-hop rows do not expose `field` and therefore were not rewritten by the entity-field selector.
- Stage621 starts from Stage619 and searches two-hop-specific composition selectors.

## Results

Stage619 broad selector transfer:

- Artifact: `runs/local/artifacts/stage619_broad_selector_transfer.json`
- Manifest: `runs/local/tmp/recursive_kbpp_selector_stage619_broad_transfer/entity_field_b8de0fec0c/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9388888888888889` / `0.9529914529914529`
- Exact/answer bits/param: `1.5104095401346604` / `1.533096620163993`
- Average train retrieval tokens/pair: `139.74357733591413`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `143`

Stage620 broad selector without two-hop:

- Artifact: `runs/local/artifacts/stage620_broad_selector_no_twohop.json`
- Exact/answer and token metrics match Stage619.
- Finding: two-hop was unchanged by the entity-field selector because the required `field` key is absent.

Stage621 two-hop selector search:

- Artifact: `runs/local/artifacts/stage621_twohop_selector_search.json`
- Source manifest: Stage619 broad transfer.
- Best template: `{domain}:{entity}:{owner}`
- Best manifest: `runs/local/tmp/recursive_kbpp_selector_stage621_twohop_selector/domain_entity_owner_de02e94096/agentkernel_lite_encdec_dataset_manifest.json`
- Exact/answer: `0.9444444444444444` / `0.9585470085470086`
- Exact/answer bits/param: `1.5193468746916703` / `1.5420339547210031`
- Average train retrieval tokens/pair: `140.11573992609536`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `130`

Stage621 ranking:

1. `{domain}:{entity}:{owner}`: answer bits/param `1.5420339547210031`; two-hop answer `1.0`
2. `{domain}:{entity}`: answer bits/param `1.5413464674473867`; two-hop answer `0.9736842105263158`
3. `{entity}:{owner}`: answer bits/param `1.5406589801737707`; two-hop answer `0.9473684210526315`
4. `{entity}`: answer bits/param `1.533096620163993`; two-hop unchanged at `0.6578947368421053`

## Interpretation

The selector rule is now operation-family specific:

- Field lookup families want `entity:field`.
- Two-hop composition wants `domain:entity:owner`.
- Entity alone is not a useful composition selector; the domain qualifier carries most of the two-hop recovery.

The best current schema-only surface is Stage621. It is still a selector surface, not a trained checkpoint: the Stage602 neural bundle is unchanged, and the gain comes from exposing compact latent binding identities in the retrieval text.
