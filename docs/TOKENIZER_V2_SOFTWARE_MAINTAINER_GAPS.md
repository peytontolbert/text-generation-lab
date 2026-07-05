# Tokenizer V2 Software Maintainer Gaps

## Purpose

This document records the token gaps to consider for a future tokenizer v2.

Do not modify the recovered v1 tokenizer for current 100M recovery:

- v1 tokenizer: `agentkernel_bytelevel_bpe_v1`
- vocab size: `1506`
- checkpoint-compatible path: keep unchanged

V2 should be a deliberate migration only after we have tokenizer hash gates, embedding/head resize, new-token initialization, suppression masks, and compatibility probes.

## Current V1 Strength

V1 already covers:

- AgentKernel dialogue/state control
- evidence and retrieval control
- sufficiency/OOD/verification markers
- memory/profile markers
- answer/rendering markers
- action-space markers
- seed software-maintenance tokens:
  - `<AK_RET_CODE>`
  - `<AK_ARTIFACT_REPAIR>`
  - `<AK_SOURCE_INSPECT>`
  - `<AK_PATCH_BUILD>`
  - `<AK_SAFE_STOP>`
  - `<AK_SOURCE_SLOTS>`
- source-copy slots:
  - `<AK_COPY_USER_SOURCE_1>` through `<AK_COPY_USER_SOURCE_24>`

## V2 Gap 1: Repo Object Tokens

Needed for compact repo-state packets:

- `<AK_REPO>`
- `<AK_PACKAGE>`
- `<AK_MODULE>`
- `<AK_FILE>`
- `<AK_DIRECTORY>`
- `<AK_SYMBOL>`
- `<AK_FUNCTION>`
- `<AK_CLASS>`
- `<AK_METHOD>`
- `<AK_VARIABLE>`
- `<AK_CONSTANT>`
- `<AK_SIGNATURE>`
- `<AK_TYPE>`
- `<AK_DOCSTRING>`
- `<AK_COMMENT>`
- `<AK_CONFIG>`
- `<AK_ENTRYPOINT>`

## V2 Gap 2: Graph And Relation Tokens

Needed for repo graph, symbol binding, dependency and impact reasoning:

- `<AK_NODE>`
- `<AK_EDGE>`
- `<AK_GRAPH_EDGE>`
- `<AK_CONTAINS>`
- `<AK_DEFINES>`
- `<AK_IMPORT>`
- `<AK_EXPORT>`
- `<AK_CALLSITE>`
- `<AK_CALL_EDGE>`
- `<AK_INHERITS>`
- `<AK_INSTANTIATES>`
- `<AK_ALIAS>`
- `<AK_TEST_COVERS>`
- `<AK_FIXTURE_USED_BY>`
- `<AK_CONFIG_CONTROLS>`
- `<AK_ENTRYPOINT_INVOKES>`
- `<AK_DEPENDS_ON>`
- `<AK_EXTERNAL_REPO_PROVIDES>`
- `<AK_FAILURE_POINTS_TO>`
- `<AK_PATCH_EDITS>`

## V2 Gap 3: Program-State Modalities

Needed for multi-view program-state representation:

- `<AK_AST>`
- `<AK_CST>`
- `<AK_CFG>`
- `<AK_DFG>`
- `<AK_IR>`
- `<AK_BYTECODE>`
- `<AK_TYPE_MAP>`
- `<AK_SYMBOL_TABLE>`
- `<AK_IMPORT_GRAPH>`
- `<AK_CALL_GRAPH>`
- `<AK_DEPENDENCY_GRAPH>`
- `<AK_TEST_GRAPH>`
- `<AK_BUILD_GRAPH>`
- `<AK_RUNTIME_TRACE>`
- `<AK_COMMIT_HISTORY>`

## V2 Gap 4: Build And Dependency Policy

Needed for intent-to-build strategy and allowed/blocked dependency control:

- `<AK_BUILD_MODE>`
- `<AK_USE_WHITELIST_IMPORT>`
- `<AK_BUILD_ON_TOP>`
- `<AK_BUILD_FROM_SCRATCH>`
- `<AK_ALLOWED_IMPORT>`
- `<AK_BLOCKED_IMPORT>`
- `<AK_ALLOWED_REPO>`
- `<AK_BLOCKED_REPO>`
- `<AK_DEPENDENCY>`
- `<AK_DEPENDENCY_VERSION>`
- `<AK_IMPORT_POLICY>`
- `<AK_REPO_POLICY>`
- `<AK_ADAPTER_REQUIRED>`
- `<AK_NO_IMPORT_ALLOWED>`

## V2 Gap 5: Edit Localization And Patch Algebra

Needed to bridge structured policy to bounded code/text edits:

- `<AK_EDIT_LOCALIZATION>`
- `<AK_TARGET_FILE>`
- `<AK_TARGET_SYMBOL>`
- `<AK_TARGET_REGION>`
- `<AK_EDIT_OPERATOR>`
- `<AK_PATCH>`
- `<AK_DIFF>`
- `<AK_HUNK>`
- `<AK_INSERT_FUNCTION>`
- `<AK_REPLACE_EXPR>`
- `<AK_REPLACE_BLOCK>`
- `<AK_WRAP_CALL>`
- `<AK_ADD_IMPORT>`
- `<AK_REMOVE_IMPORT>`
- `<AK_ADD_TEST>`
- `<AK_UPDATE_CONFIG>`
- `<AK_CREATE_FILE>`
- `<AK_EDIT_FILE>`
- `<AK_DELETE_FILE>`
- `<AK_RENAME_SYMBOL>`
- `<AK_MINIMAL_DIFF>`

## V2 Gap 6: Verification And Failure Tokens

Needed for verifier-driven repair and failure diagnosis:

- `<AK_VERIFIER_RESULT>`
- `<AK_VERIFY_PASS>`
- `<AK_VERIFY_FAIL>`
- `<AK_TEST_RESULT>`
- `<AK_TEST_PASS>`
- `<AK_TEST_FAIL>`
- `<AK_LINT_RESULT>`
- `<AK_TYPECHECK_RESULT>`
- `<AK_BUILD_RESULT>`
- `<AK_RUNTIME_RESULT>`
- `<AK_FAILURE_LOG>`
- `<AK_STACK_TRACE>`
- `<AK_ERROR_TYPE>`
- `<AK_ROOT_CAUSE>`
- `<AK_FAILURE_MODE>`
- `<AK_REPAIR_ACTION>`
- `<AK_ROLLBACK>`
- `<AK_RERUN_TEST>`

## V2 Gap 7: Denoise And Repair Tokens

Needed for the repair layer after verifier feedback:

- `<AK_DENOISE>`
- `<AK_REPAIR_OUTPUT>`
- `<AK_REPAIR_PATCH>`
- `<AK_REPAIR_INTERNAL_LEAK>`
- `<AK_REPAIR_SHORT_OUTPUT>`
- `<AK_REPAIR_REPETITION>`
- `<AK_REPAIR_WRONG_SURFACE>`
- `<AK_REPAIR_SYNTAX_ERROR>`
- `<AK_REPAIR_FAILED_TEST>`
- `<AK_ABSTAIN_UNRECOVERABLE>`
- `<AK_MASK_SPAN>`
- `<AK_CORRUPTED_STATE>`
- `<AK_CLEAN_STATE>`
- `<AK_REPAIR_CANDIDATE>`

## V2 Gap 8: Control Actions

Needed for a typed software-maintainer action policy:

- `<AK_ACTION_RETRIEVE_MORE>`
- `<AK_ACTION_ABSTAIN>`
- `<AK_ACTION_PLAN>`
- `<AK_ACTION_READ_FILE>`
- `<AK_ACTION_SEARCH_REPO>`
- `<AK_ACTION_BIND_SYMBOL>`
- `<AK_ACTION_LOCALIZE_EDIT>`
- `<AK_ACTION_SELECT_OPERATOR>`
- `<AK_ACTION_GENERATE_PATCH>`
- `<AK_ACTION_RUN_VERIFIER>`
- `<AK_ACTION_REPAIR>`
- `<AK_ACTION_FINISH>`
- `<AK_ACTION_SAFE_STOP>`

## V2 Gap 9: Security, Provenance, And License

Needed before scaling mined datasets:

- `<AK_SOURCE_PROVENANCE>`
- `<AK_LICENSE>`
- `<AK_LICENSE_ALLOWED>`
- `<AK_LICENSE_BLOCKED>`
- `<AK_SECURITY_POLICY>`
- `<AK_SECRET_DETECTED>`
- `<AK_PII_DETECTED>`
- `<AK_CONTAMINATION_RISK>`
- `<AK_SPLIT_LOCKED>`
- `<AK_GOLDEN_EVAL>`
- `<AK_QUARANTINE>`
- `<AK_HUMAN_REVIEW>`

## V2 Gap 10: Telemetry And Learning Signals

Needed for model-internal interpretability and training repair:

- `<AK_ROW_LOSS>`
- `<AK_TOKEN_LOSS>`
- `<AK_LOGIT_MARGIN>`
- `<AK_CONFIDENCE>`
- `<AK_ENTROPY>`
- `<AK_FORGETTING_EVENT>`
- `<AK_GRADIENT_NORM>`
- `<AK_INFLUENCE_HELPFUL>`
- `<AK_INFLUENCE_HARMFUL>`
- `<AK_COUNTERFACTUAL_SIBLING>`
- `<AK_HARD_NEGATIVE>`
- `<AK_NEIGHBOR_CELL>`
- `<AK_SHORTCUT_RISK>`

## V2 Migration Gates

Before using any v2 tokenizer in training:

1. Freeze v1 as the checkpoint-compatible tokenizer.
2. Create a versioned v2 tokenizer config and tokenizer JSON.
3. Assign stable IDs for new tokens.
4. Generate a token inventory card.
5. Resize encoder embeddings, decoder embeddings, and LM head.
6. Define initialization for new embeddings.
7. Rebuild token-ID suppression masks.
8. Rebuild internal/control token guards.
9. Add tokenizer hash enforcement to trainer preflight.
10. Add compatibility tests against v1 checkpoints.
11. Run tiny no-training tokenizer round-trip tests.
12. Run non-executing dataset/compiler audits.
13. Only then consider a tiny structured-head probe.

## Near-Term Rule

Do not wait on v2 to continue recovery.

For current training recovery, represent these concepts as:

- structured feature IDs
- manifest fields
- graph node/edge types
- action labels
- loss masks
- dataset judge routes

V2 is for compact serialized program-state packets and future bounded decoding, not for reopening decoder CE now.
