# Stage9708 Symbol-Binding Visible Evidence Manifest

Stage9708 responds to the Stage9707 residual collapse by making the missing symbol-binding evidence explicit before another target-100M probe.

## Added Evidence

- Opaque query candidate nodes beyond repo/file/contains.
- Candidate node types for module, symbol, test, and retrieval-gap evidence.
- Relation-count features for call/import/test candidate compatibility.
- Counterfactual rows that keep the same query kind while changing whether the candidate is resolvable, ambiguous, or requires retrieval.

## Guardrails

- No decoder CE, runtime, Gemma, harness, source/body emission, or promotion authority is opened.
- Target labels remain outside encoder-facing fields.
- The audit blocks if query kind or any single feature still solves the action label.

## Metrics

- Passed: `True`
- Rows: `92`
- Synthetic counterfactual rows: `28`
- Source query-kind baseline: `0.640625`
- Repaired query-kind baseline: `0.445652`
- Strongest single-feature baseline: `0.75`

## Next

Run Stage9709 contract-only preflight on the Stage9708 visible-evidence symbol-binding manifest; do not execute target-100M until query-kind and single-feature baselines remain below ceilings.
