# Software Maintainer Action And Feature Registry

This file records the recovered maintainer-control map for the 100M model. It is the bridge from local `/arxiv/datasets` and `/arxiv/repositories` into typed curriculum manifests.

The active training thesis is:

```text
software maintenance = structured state transitions first, bounded decoding second
```

The 100M model should not learn from raw code blobs directly. Rows must pass through the dataset judge, receive a curriculum route, and enable only the losses that match their objective.

## Active Hierarchy

```text
intent-to-build strategy
-> repo_state_graph_v1
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder arguments
-> bounded decoder CE
-> denoise repair
-> controlled harness
```

## Build Strategy

Core build modes:

- `USE_WHITELIST_IMPORT`: use an allowed library/API directly.
- `BUILD_ON_TOP`: use allowed repository/library capability and write glue or adapter code.
- `BUILD_FROM_SCRATCH`: implement without blocked or missing dependencies.

Recovered policy fields:

- `build_mode`
- `allowed_import_policy`
- `blocked_import_policy`
- `repo_dependency_policy`
- `file_plan`
- `action_sequence`
- `verification_mode`

These answer whether code generation is even legal before the decoder receives a row.

## Repo State Graph

`repo_state_graph_v1` is the substrate for real software-maintainer cognition.

Node types:

- `repo`, `file`, `module`, `symbol`, `function`, `class`, `method`
- `import`, `callsite`, `test`, `fixture`, `config`, `entrypoint`
- `dependency`, `external_repo`, `verifier`, `failure_log`

Edge types:

- `contains`, `defines`, `imports`, `exports`, `calls`
- `instantiates`, `inherits`, `test_covers`, `fixture_used_by`
- `config_controls`, `entrypoint_invokes`, `depends_on`
- `external_repo_provides`, `failure_points_to`, `patch_edits`
- `verifier_checks`, `symbol_aliases`, `language_boundary`

Anti-cheat rules:

- Graph IDs must be opaque row-local IDs.
- IDs must not encode objective labels.
- Objective metadata stays outside model input.
- Query node ID alone must not solve the target.
- Degree profile alone must not solve action or target.


## Semantic Presentation And User Intent

Semantic presentation is a first-class row field, not a synonym for free-form decoder text. Future transition records must keep user intent, semantic surface, and objective labels separate so the model cannot solve a task by copying visible target markers.

Recovered semantic presentation surfaces:

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

Recovered user-intent fields:

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

Required anti-cheat rule:

```text
semantic_presentation != objective_label
requested_output_type != target_action
intent_type alone must not solve build_mode/action/surface
```

Rows that expose direct target labels in user-intent or presentation fields must route to `NEEDS_HUMAN_REVIEW` or a neutralization patch queue before they can create gradients.

## Objective Families

The compiler should produce separate manifests:

- `intent_to_build_strategy`
- `repo_capability_catalog`
- `repo_state_graph_v1`
- `symbol_binding`
- `edit_localization`
- `patch_operator`
- `verifier_repair`
- `bounded_decoder_arguments`
- `bounded_decoder_ce`
- `output_repair_denoise`
- `verifier_feedback`
- `long_output_holdout`
- `promotion_regression`

Each family gets its own shortcut audit, loss card, telemetry card, and authority card.

## Actions

High-level actions:

- `RETRIEVE_MORE`
- `ABSTAIN_UNSAFE`
- `HOLD_LONG_OUTPUT`
- `RENDER_USER_FACING`
- `REPAIR_INTERNAL_LEAK`
- `REPAIR_SHORT_OUTPUT`
- `GENERATE_REPAIR_PLAN`
- `GENERATE_BOUNDED_CODE`
- `GENERATE_PATCH_HUNK`
- `GENERATE_TEST_PLAN`
- `RUN_VERIFIER`
- `REPAIR_PATCH`
- `FINISH`

Build actions:

- `SELECT_IMPORT`
- `REJECT_IMPORT`
- `SEARCH_ALLOWED_REPO`
- `READ_ALLOWED_SOURCE`
- `BUILD_WRAPPER`
- `BUILD_FROM_SCRATCH`
- `CREATE_FILE`
- `EDIT_FILE`
- `CREATE_TEST`
- `UPDATE_CONFIG`
- `RUN_VERIFIER`
- `REPAIR_PATCH`
- `FINISH`

Binding actions:

- `BIND_CALL_TO_SYMBOL`
- `BIND_IMPORT_TO_MODULE`
- `BIND_TEST_TO_SYMBOL`
- `BIND_FAILURE_TO_SYMBOL`
- `RETRIEVE_MORE`
- `ABSTAIN_UNBOUND`

Patch operators:

- `MODIFY_EXISTING_SYMBOL`
- `INSERT_FUNCTION`
- `REPLACE_EXPR`
- `WRAP_CALL`
- `ADD_IMPORT`
- `ADD_TEST_CASE`
- `UPDATE_CONFIG_FIELD`
- `CREATE_FILE`
- `BUILD_ADAPTER`
- `ROLLBACK_PATCH`
- `RETRIEVE_MORE`
- `ABSTAIN_UNSAFE`

Verifier repair actions:

- `DIAGNOSE_FAILURE`
- `RERUN_VERIFIER`
- `LOCALIZE_FAILURE`
- `REPAIR_SYNTAX`
- `REPAIR_ASSERTION`
- `REPAIR_IMPORT`
- `REPAIR_API_CALL`
- `ROLLBACK_OR_ABSTAIN`
- `RETRIEVE_MORE`

## Dataset Judge Routes

Objective-aware row routes:

- `KEEP_STRUCTURED`
- `KEEP_BOUNDED_DECODER`
- `HOLD_LONG_OUTPUT`
- `USE_FOR_DENOISE_REPAIR`
- `USE_AS_NEGATIVE`
- `NEEDS_RETRIEVAL`
- `QUARANTINE_LABEL_CONFLICT`
- `DROP_DUPLICATE`
- `NEEDS_HUMAN_REVIEW`

A row can be valid for one objective and unsafe for another. For example, a 30k-character HTML row can be useful as `HOLD_LONG_OUTPUT` or a budget classifier negative, but it must not train bounded decoder CE under a 768-token budget.

## Critical Judge Signals

- target over decoder budget
- long blob
- HTML/doc fragment
- decoder target truncated
- raw internal token in decoder target
- raw text leak in structured objective
- short or junk target
- degenerate repetition target
- missing evidence but decode allowed
- budget bad but decode allowed
- ambiguous action label
- surface role conflict
- duplicate semantic key
- split overlap
- shortcut dominated feature
- teacher/verifier disagreement

## Gate Features

The hard gate is not only learned:

```text
effective_decode_allowed =
    learned_decode_allowed
    AND deterministic_budget_ok
    AND action_allows_decode
    AND evidence_allows_decode
    AND junk_ranker_route allows decode
```

Important features:

- `deterministic_budget_ok`
- `target_token_len`
- `long_blob`
- `html_doc_fragment`
- `raw_internal_token_present`
- `source_anchor_present`
- `direct_evidence_present`
- `decision_sufficient_evidence_present`
- `missing_evidence`
- `verifier_failure_type`
- `import_allowed`
- `import_blocked`
- `repo_capability_match`
- `symbol_binding_confidence`
- `edit_region_available`
- `tests_available`
- `junk_ranker_route`
- `junk_ranker_reason_bits`

## Loss Routing

Every manifest row must declare which losses can create gradients.

Examples:

- `KEEP_STRUCTURED`: classifier/control losses only.
- `KEEP_BOUNDED_DECODER`: bounded decoder CE only.
- `HOLD_LONG_OUTPUT`: no decoder CE.
- `USE_FOR_DENOISE_REPAIR`: denoise objective, not raw generation.
- `USE_AS_NEGATIVE`: abstain/block/retrieve control losses.

The compiler should emit a loss-mask card for every manifest. Decoder CE stays closed unless the row is budget-clean, authority-clean, shortcut-audited, and loss-mask authorized.

## Decoder Reopen Contract

Bounded decoder CE may only be considered for rows satisfying all of:

- `decoder_budget_ok == true`
- `deterministic_budget_ok == true`
- `long_blob == false`
- `html_doc_fragment == false`
- authority rows are zero
- no copied target text in model input
- row loss mask authorizes `decoder_ce`
- row and token caps are enforced
- telemetry artifacts are declared
- no final checkpoint export

## What `/arxiv` Should Feed

`/arxiv/repositories` should feed:

- repo capability catalog
- repo-state graph seeds
- symbol/import/test binding rows
- edit localization rows
- patch operator rows
- verifier-repair rows
- bounded decoder argument rows

`/arxiv/datasets` should feed:

- prior SWE task rows after schema audit
- long-output holdout rows
- retrieve/abstain negatives
- denoise repair candidates
- promotion regression rows

No `/arxiv` row should reach model gradients until it has a route, authority card, loss mask, shortcut audit, duplicate check, and budget/evidence status.

