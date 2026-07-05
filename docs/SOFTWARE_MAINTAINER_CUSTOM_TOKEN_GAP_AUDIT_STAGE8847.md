# Stage8847 Software Maintainer Custom Token Gap Audit

## Status

Stage8847 audits the recovered 1506-vocab AgentKernel tokenizer against the current 100M software-maintainer objective.

This is an audit/design artifact only. It opens no model execution, decoder CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, or promotion authority.

## Recovered Strength

The recovered tokenizer is not generic. It already has a strong AgentKernel control vocabulary:

- dialogue/state tokens: user, chat, plan, state, context
- evidence/retrieval tokens: evidence, retrieve, rerank, context IDs, retrieval modes
- sufficiency/OOD tokens: sufficient, insufficient, uncertain, OOD, needs verification
- answer/rendering tokens: answer, render, JSON, content, end
- memory/profile tokens: memory read/write/update, profile slots, preferences
- verification tokens: verify, reflect, check fact, check consistency, check evidence
- action-space tokens: code, artifact, retrieval, respond, structured actions
- software-maintenance seed tokens: return code, artifact repair, source inspect, patch build, safe stop, source slots
- source-copy slot tokens: `<AK_COPY_USER_SOURCE_1>` through `<AK_COPY_USER_SOURCE_24>`

This is enough to support high-level structured policy and bounded rendering if the manifests preserve row-level schema and loss masks.

## Missing Dedicated Software-Maintenance Tokens

The recovered tokenizer does not contain dedicated object/state tokens for the repo-graph spine now required by the software maintainer.

Missing likely primitives:

- `<AK_REPO>`
- `<AK_FILE>`
- `<AK_MODULE>`
- `<AK_SYMBOL>`
- `<AK_FUNCTION>`
- `<AK_CLASS>`
- `<AK_METHOD>`
- `<AK_IMPORT>`
- `<AK_CALLSITE>`
- `<AK_TEST>`
- `<AK_FIXTURE>`
- `<AK_CONFIG>`
- `<AK_ENTRYPOINT>`
- `<AK_DEPENDENCY>`
- `<AK_AST>`
- `<AK_GRAPH_EDGE>`
- `<AK_FAILURE_LOG>`
- `<AK_STACK_TRACE>`
- `<AK_VERIFIER_RESULT>`
- `<AK_DIFF>`
- `<AK_PATCH>`
- `<AK_EDIT_OPERATOR>`
- `<AK_BUILD_MODE>`
- `<AK_ALLOWED_IMPORT>`
- `<AK_BLOCKED_IMPORT>`
- `<AK_ACTION_REPAIR>`
- `<AK_ACTION_RETRIEVE_MORE>`
- `<AK_ACTION_ABSTAIN>`

These concepts still exist in the recovered curriculum as structured fields, graph node types, edge types, loss-mask labels, and manifest columns. They are not yet compact tokenizer-native markers.

## Interpretation

This is not a blocker for structured heads.

For the current recovery path, software-maintenance state should remain represented by:

- `structured_feature_ids`
- schema fields
- graph node/edge objects
- action labels
- loss masks
- dataset judge routes
- manifest JSON fields

The model can learn structured heads from those tensors without adding tokenizer tokens.

It is a blocker for broad serialized repo-state decoding if we later try to flatten repo graphs into text packets. Without dedicated repo/file/symbol/import/test/failure/patch tokens, the serialized packet relies more on ordinary BPE fragments and JSON strings, which weakens compactness and makes shortcut/leak auditing harder.

## Checkpoint Compatibility Rule

Do not casually add new special tokens to the recovered 1506 vocabulary.

Adding tokens changes:

- tokenizer hash
- `vocab_size`
- embedding matrix shape
- LM head shape
- checkpoint compatibility
- token-ID suppression masks
- any preserved artifact expecting vocab size `1506`

Therefore, token expansion requires a separate audited migration:

1. preserve the current 1506-vocab tokenizer as `agentkernel_bytelevel_bpe_v1`
2. design a new tokenizer version, e.g. `agentkernel_software_maintainer_bpe_v2`
3. allocate new software-maintenance tokens after the existing 1506 IDs
4. initialize new embeddings safely
5. resize tied/untied decoder heads consistently
6. update tokenizer hash gates
7. rebuild token-ID suppression masks
8. run compatibility probes before any training

Until that migration exists, keep the 1506-vocab path as the canonical recovered training target.

## Recommended Near-Term Path

Use structured tensors rather than tokenizer expansion:

- repo graph: node/edge typed IDs
- symbol binding: query node ID + candidate node IDs + binding action labels
- edit localization: target file/symbol/config/test labels
- patch operator: operator class + bounded arguments
- verifier repair: failure class + repair action + target object
- intent/build policy: build mode, import policy, repo policy, file plan

For bounded decoder CE, render only compact argument text after the structured heads decide the legal action and target. Do not make the decoder infer repo graph structure from raw serialized text.

## Future Token Expansion Candidate

If the project later needs tokenizer-native software-state packets, create a v2 candidate with these groups:

### Repo Object Tokens

`<AK_REPO>`, `<AK_FILE>`, `<AK_MODULE>`, `<AK_SYMBOL>`, `<AK_FUNCTION>`, `<AK_CLASS>`, `<AK_METHOD>`, `<AK_CONFIG>`, `<AK_ENTRYPOINT>`

### Relation Tokens

`<AK_IMPORT>`, `<AK_EXPORT>`, `<AK_CALLSITE>`, `<AK_CALL_EDGE>`, `<AK_TEST_COVERS>`, `<AK_DEPENDS_ON>`, `<AK_FAILURE_POINTS_TO>`, `<AK_PATCH_EDITS>`

### Evidence/Failure Tokens

`<AK_FAILURE_LOG>`, `<AK_STACK_TRACE>`, `<AK_VERIFIER_RESULT>`, `<AK_TEST_RESULT>`, `<AK_LINT_RESULT>`, `<AK_TYPECHECK_RESULT>`

### Edit Tokens

`<AK_EDIT_OPERATOR>`, `<AK_PATCH>`, `<AK_DIFF>`, `<AK_INSERT_FUNCTION>`, `<AK_REPLACE_EXPR>`, `<AK_ADD_IMPORT>`, `<AK_ADD_TEST>`, `<AK_UPDATE_CONFIG>`

### Build/Dependency Tokens

`<AK_BUILD_MODE>`, `<AK_USE_WHITELIST_IMPORT>`, `<AK_BUILD_ON_TOP>`, `<AK_BUILD_FROM_SCRATCH>`, `<AK_ALLOWED_IMPORT>`, `<AK_BLOCKED_IMPORT>`, `<AK_DEPENDENCY>`

## Next

Next best step:

`stage8848_special_token_guard_unification_design`

It should not expand the tokenizer. It should first unify:

- regex token guards
- tokenizer-ID suppression masks
- `<AK_...>` route authorization
- legacy internal-token denoise routing
- trainer tokenizer-hash preflight
- model-output packet token telemetry
