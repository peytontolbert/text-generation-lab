# Symbol Binding Recovery Status

Latest relevant stages:

- `8604`: extracted leak-clean symbol/import/test binding candidates from `/arxiv/repositories`.
- `8605`: blocked training because candidates were imbalanced and had no counterfactual siblings.
- `8610`: built counterfactual sibling groups.
- `8611`: confirmed sibling obligations are complete but training remains blocked.
- `8612`: added required structured telemetry contract.
- `8617`: mined true closed-authority `BIND_TEST_TO_SYMBOL` seed rows from test-file calls to non-test repo definitions.
- `8618`: merged the test-bind patch into symbol-binding candidates and rebuilt counterfactual obligations.
- `8619`: audited the patched surface; test-bind/query coverage is restored, but training remains closed due majority-action baseline dominance.

## What Is Clean

Stage8604/8610 rows are closed-authority:

- no raw source in model input
- no decoder CE
- no runtime reward
- no body/source emission
- no Gemma/harness/scoring
- opaque IDs
- endpoint failures: `0`

Stage8610 and Stage8618 have complete sibling obligations:

- `POSITIVE_ORIGINAL`
- `EVIDENCE_REMOVED_OR_RETRIEVE`
- `CONTRASTIVE_BOUNDARY_SIBLING`

Stage8617 recovered:

- `BIND_TEST_TO_SYMBOL` seed rows: `121`
- repos represented: `16`
- endpoint failures: `0`
- label ID leaks: `0`
- raw source rows: `0`
- authority rows: `0`
- decoder rows: `0`

Stage8618 rebuilt the counterfactual surface:

- source rows: `1068`
- output rows: `348`
- sibling groups: `116`
- `BIND_TEST_TO_SYMBOL` rows in counterfactual surface: `24`
- query kind counts: `callsite: 132`, `import: 144`, `test: 72`
- all three obligations represented for every group.

## What Still Blocks Training

The current patch is not model-ready because action balance is still too retrieve-heavy:

- missing actions: none
- missing query kinds: none
- missing split/action cells: none
- missing split/query cells: none
- majority action baseline exact: `0.5287`
- query-kind action baseline exact: `0.5287`
- model-ready rows: `0`

This is not a trainer bug. It is a data/compiler distribution gap. Test-bind coverage is restored, but `RETRIEVE_MORE` still dominates enough that training remains blocked.

## Next Required Data Patch

Add or rebalance non-`RETRIEVE_MORE` symbol-binding rows so `majority_action_baseline_exact < 0.5`.

Priority additions:

- more `BIND_IMPORT_TO_MODULE` rows,
- more `BIND_TEST_TO_SYMBOL` contrastive rows,
- more `ABSTAIN_UNBOUND` near-miss rows,
- same-query contrastive test rows where test evidence should bind versus retrieve,
- import/test retrieve controls that are not trivially separable by query kind.

Target transition:

```text
test node/query
+ source/module/call evidence
-> BIND_TEST_TO_SYMBOL | RETRIEVE_MORE | ABSTAIN_UNBOUND
```

The patch must preserve:

- opaque IDs
- no raw source text in model input
- split coverage
- sibling groups
- shortcut baselines below ceiling
- structured telemetry required before execution

## Telemetry Required Before Native Probe

Future structured probes must emit:

- `row_field_logits.jsonl`
- `row_field_losses.jsonl`
- `field_exact_by_split.json`
- `field_exact_by_cell.json`
- `confusion_matrix.json`
- `margin_confidence_entropy.jsonl`
- `high_confidence_wrong_rows.jsonl`
- `row_gradient_norms.jsonl`
- `failure_bucket_card.json`
- `module_delta_norms.json`

No structured capability claim should be accepted without those artifacts.

