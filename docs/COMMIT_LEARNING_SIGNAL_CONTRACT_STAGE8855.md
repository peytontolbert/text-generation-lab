# Stage8855 Commit Learning Signal Contract

Passed: `True`

This stage records how commits should become learning signals without mining repositories yet.

Core rule: never train on raw commits as one example. Decompose commits into causal edit units, classify hunks as core/supporting/incidental/noise, and emit structured labels before any bounded decoder target is considered.

Rows: `10`
Contract-ready rows: `10`
Commit mining authorized: `False`
Training authorized: `False`
Decoder CE authorized: `False`

Target surfaces:

- `edit_localization`
- `patch_operator`
- `file_plan`
- `symbol_binding`
- `verifier_repair`
- `action_sequence`
- `needs_verification`
- `retrieval_coverage`

Commit size policy:

- small commits: direct structured labels and bounded decoder candidates only if compact and clean
- medium commits: segment into causal units first
- large commits: use for decomposition, retrieval/context, repo graph, and verifier planning; decoder targets stay blocked
