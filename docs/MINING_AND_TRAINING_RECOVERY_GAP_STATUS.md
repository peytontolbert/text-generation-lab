# Mining And Training Recovery Gap Status

Current frontier: `Stage8619`.

## Direct Answer

No, broad mining is not fully recovered yet.

Recovered enough for limited work:

- `/arxiv` corpus inventory
- repo capability catalog seeds
- repo-state graph seed rows
- symbol/import/test binding candidate extraction
- symbol-binding counterfactual patching
- true `BIND_TEST_TO_SYMBOL` seed recovery
- symbol-binding counterfactual rebuild with test-bind coverage
- dataset judge/ranker scaffold
- curriculum compiler scaffold
- loss-mask card
- counterfactual obligation audit
- structured telemetry contract
- semantic/user-intent/mining concepts from recent Codex sessions

Not recovered enough for broad mining:

- `intent_to_build_strategy` miner
- `edit_localization` miner
- `patch_operator` miner
- `verifier_repair` miner
- `bounded_decoder_arguments` miner
- `output_repair_denoise` miner

Do not start broad `/arxiv` mining until those are restored.

## Recovered From Sessions

The session recovery pass found these concept groups:

- semantic presentation
- user intent
- mining
- curriculum compiler
- dataset judge
- training telemetry
- software maintenance

Important recovered details:

- The model needs semantic presentation surfaces, not raw text only.
- User intent must include repo QA, repo repair, code generation, test generation, config update, dependency decision, debugging, and maintainer explanation.
- Mining must produce action-value counterfactuals: action A failed, action B passed, action C was risky, action D needed tests first.
- Long-horizon repo state matters: invariants, dependencies, tests, architecture, user intent, and prior failed attempts.
- Verifier discovery and baseline-passing verifier gates are required before runtime or guarded accepts.
- Non-Python repair-control surfaces previously used `ACTION_HOLD` vs `ACTION_REJECT` and `EVIDENCE_FAILURE` vs `EVIDENCE_HOLD`.
- Hard negatives and HOLD evidence are first-class mining targets.

## Semantic Presentation Surfaces

Recovered target surfaces:

- `maintainer_answer`
- `repair_plan`
- `bounded_patch_hunk`
- `test_plan`
- `repo_qa_answer`
- `retrieve_more_answer`
- `abstain_unsafe_answer`
- `verifier_failure_summary`
- `symbol_binding_decision`
- `edit_localization_decision`
- `patch_operator_decision`

These must remain separated from local objective labels. The model should learn semantic state/action first, then render the appropriate surface.

## User Intent Fields

Recovered fields:

- `intent_type`
- `requested_output_type`
- `target_language`
- `repo_scope`
- `allowed_imports`
- `blocked_imports`
- `available_repositories`
- `file_creation_allowed`
- `modify_existing_allowed`
- `test_required`
- `verification_mode`
- `risk_tolerance`
- `budget_constraints`

Build strategy remains:

- `USE_WHITELIST_IMPORT`
- `BUILD_ON_TOP`
- `BUILD_FROM_SCRATCH`

## Mining Must Produce

Every mined row family needs:

- source inventory card
- route card
- authority card
- loss-mask card
- counterfactual obligation card
- shortcut baseline card
- duplicate semantic key card
- split-overlap card
- budget/evidence card
- telemetry contract card

## Current Safe Mining Scope

Allowed next limited mining:

- symbol-binding action rebalance rows, especially non-`RETRIEVE_MORE` rows
- same-query test contrastives where test evidence should bind versus retrieve
- additional import-module and abstain-unbound near-miss rows

Reason:

- symbol-binding extractor exists
- true `BIND_TEST_TO_SYMBOL` seed rows now exist
- counterfactual audit exists
- telemetry contract exists
- current blocker is majority-action baseline dominance, not missing test-bind coverage

Blocked broad mining:

- intent-to-build
- edit localization
- patch operator
- verifier repair
- bounded decoder arguments
- output repair denoise

Those need dedicated miners and audits restored first.

