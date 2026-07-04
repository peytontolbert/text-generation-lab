# Stage8615 Recovered Variable Ledger

Stage8615 scanned recent Codex session archives to recover training variables, labels, routes, and stage names that were not fully represented in the reconstructed post-loss repo. This is a recovery ledger, not a training authorization.

## Source

- Sessions root: `/home/peyton/.codex/sessions`
- Recent files scanned: 260
- Files with maintainer/training hits: 260
- Raw artifact: `runs/local/artifacts/stage8615_recovered_variable_ledger/recovered_variable_ledger.json`
- Filtered artifact: `runs/local/artifacts/stage8615_recovered_variable_ledger/maintainer_filtered_ledger.json`

## Recovery Buckets

The scan recovered dense evidence in the areas that matter for the 100M software-maintainer objective:

- `decoder`: 5269 hits
- `semantic_presentation`: 4394 hits
- `verifier_loop`: 4019 hits
- `routing_authority`: 3275 hits
- `mining_judge`: 2660 hits
- `training_telemetry`: 2275 hits
- `counterfactual`: 495 hits
- `software_graph`: 247 hits

These buckets confirm that the lost work was not just decoder code. It included routing authority, semantic presentation, verifier loops, mining/judge logic, and training telemetry.

## Recovered Behavior-Value Labels

These labels should be restored as first-class closed-loop policy concepts:

- `BV_ACCEPT_READY`
- `BV_NEEDS_VERIFIER`
- `BV_REJECT_OR_ABSTAIN`
- `BV_FALSE_ACCEPT_RISK`
- `CANDIDATE_PASS_VERIFIED`
- `CANDIDATE_NEEDS_TEST`
- `CANDIDATE_FAIL_BEHAVIOR`
- `CANDIDATE_FAIL_INTERFACE`
- `NO_VERIFY`
- `SELECT_NO_VERIFY`
- `SELECT_COPY_VERIFY`
- `SELECT_GEN_EDIT_VERIFY`
- `COPY_VERIFY`
- `GEN_EDIT_VERIFY`

Interpretation:

- A candidate can be correct-looking but still require verifier evidence.
- `NO_VERIFY` is not a neutral state; it is a risk route.
- `SELECT_COPY_VERIFY` and `SELECT_GEN_EDIT_VERIFY` indicate old selector objectives that chose between copying a verified candidate and generating/editing/verifying a new candidate.
- `BV_FALSE_ACCEPT_RISK` must be treated as a negative control concept in candidate selection and verifier-repair objectives.

## Recovered Control Labels

These labels restore the control side of the maintainer loop:

- `ACTION_HOLD`
- `ACTION_REJECT`
- `CONTROL_HOLD_FOR_MORE_EVIDENCE`
- `CONTROL_REPAIR_OR_ABSTAIN`
- `CONTROL_REJECT_MISSING_RETURN_BEHAVIOR`
- `CONTROL_REJECT_TRIVIAL_CANDIDATE`
- `CONTROL_REJECT_MISSING_CALL_FEATURES`
- `CONTROL_REJECT_TRIVIAL_OR_MISSING_CALL_FEATURES`
- `CLOSED_LOOP_NEXT_ACTION`
- `REPAIR_OR_ABSTAIN`
- `REPAIR_OR_ABSTAIN_AFTER_NODE_FAIL`

Interpretation:

- The maintainer model must learn conservative HOLD/REJECT behavior, not only patch emission.
- Missing call features and missing return behavior were recurring rejection reasons.
- `CLOSED_LOOP_NEXT_ACTION` should be restored as a transition target for verifier-feedback episodes.

## Recovered Evidence Labels

These labels restore the evidence status plane:

- `EVIDENCE_HOLD`
- `EVIDENCE_FAILURE`
- `EVIDENCE_FAIL_BEHAVIOR`
- `EVIDENCE_FAIL_INTERFACE`
- `EVIDENCE_NEEDS_TEST`
- `EVIDENCE_PASS_CUDA_EXEC`
- `EVIDENCE_PASS_PY_PROBE`
- `SOURCE_AUDIT`
- `SOURCE_FAMILY`
- `SOURCE_ROWS`
- `CONTEXT_REQUIRED_NO_BODY_CLAIM`
- `NEEDS_REPO_CONTEXT_VERIFIER`

Interpretation:

- Evidence is not binary. It can prove behavior, interface, tests, runtime, or source locality.
- Some rows must route to HOLD because context is required and body/source emission is not authorized.
- Verifier evidence needs to be represented explicitly before candidates can be accepted.

## Recovered Graph And Symbol Families

Recovered graph families:

- `GRAPH_DATA_RUNTIME_IO`
- `GRAPH_INTERFACE_BOUNDARY`
- `GRAPH_MODEL_TRAIN_EVAL`
- `GRAPH_AGENT_TOOLING`
- `GRAPH_GENERIC_LIBRARY`
- `GRAPH_TEST_VERIFIER`

Recovered symbol families:

- `SYM_BUILD_OR_RUNTIME`
- `SYM_TEST_OR_VERIFIER`
- `SYM_AGENT_OR_TOOL`
- `SYM_API_HANDLER`
- `SYM_CLI_ENTRYPOINT`
- `SYM_CONFIG_ENV`
- `SYM_DATA_IO`
- `SYM_EVAL_OR_METRIC`
- `SYM_GENERIC_LIBRARY`
- `SYM_MODEL_OR_LAYER`
- `SYM_SERIALIZATION`
- `SYM_TRAINING_OR_OPTIM`

Interpretation:

- `repo_state_graph_v1` should not stay limited to calls/imports/tests. It needs graph family tags for data/runtime IO, interface boundaries, model train/eval paths, agent tooling, generic libraries, and verifier/test relations.
- These families are useful for symbol binding, edit localization, patch operator selection, and verifier repair.

## Recovered Semantic Presentation Fields

Recovered semantic presentation variables:

- `AK_INTENT`
- `AK_TASK_TYPE`
- `AK_ACTION_RESPOND`
- `AK_ACTION_ASK_USER`
- `AK_ACTION_EXTENSION_REQUEST`
- `AK_ACTION_SAVE_MEMORY`
- `AK_RETRIEVE`
- `AK_VERIFY`
- `AK_STRUCTURED`
- `AK_FIELD`
- `AK_FIELD_NAME`
- `AK_FIELD_VALUE`
- `AK_FIELDS`
- `AK_SLOT`
- `AK_SLOT_NAME`
- `AK_SLOT_VALUE`
- `AK_CONTENT`
- `AK_GOAL`
- `AK_DOMAIN`
- `AK_TONE`
- `AK_CONSTRAINT`
- `AK_FRESHNESS`

Interpretation:

- The model needs a structured semantic presentation layer, not raw prompt text only.
- User intent, goal, domain, tone, constraints, freshness, and field slots should be encoded as structured state fields when building intent-to-build, repo QA, maintainer answer, and verifier-repair rows.

## Recovered Candidate Selection And Verification Concepts

Important recovered concepts:

- `CANDIDATE_EXACTNESS`
- `NONEXACT_PAYLOAD_CANDIDATE`
- `ACCEPT_CANDIDATE`
- `REJECT_CANDIDATE`
- `ACCEPT_READY`
- `ACCEPT_GUARDED_EXACT`
- `ACCEPT_SCHEMA_AST_MATERIALIZER_AFTER_OBSERVED_PYCOMPILE_PASS`
- `TARGET_SPECIFIC_VISIBLE_CONTRACT_PASS`
- `VISIBLE_BEHAVIOR_SMOKE_PASS`
- `VERIFY_TOP1`
- `VERIFY_FULL_TOP5`
- `SELECT_SCHEMA_AST_TOPK_CANDIDATE_1`
- `SELECT_SCHEMA_AST_TOPK_CANDIDATE_2`
- `SELECT_SCHEMA_AST_TOPK_CANDIDATE_3`
- `SELECT_SCHEMA_AST_TOPK_CANDIDATE_4`
- `SELECT_SCHEMA_AST_TOPK_CANDIDATE_5`
- `BEST_OF_N_POLICY`

Interpretation:

- The old system had candidate-selection surfaces, top-k schema/AST candidate routing, and verifier-backed acceptance.
- Rebuild should include selector objectives before broad code generation:
  - rank candidate payloads,
  - reject nonexact candidates,
  - prefer verified candidates,
  - select best-of-n only under verifier-backed evidence.

## Recovered Non-Python Repair-Control Surface

Recovered label:

- `AK_NONPYTHON_REPAIR_CONTROL_BALANCED_STATUS_FEATURE_V1`

Recovered supporting details:

- Languages included `c_family`, `rust`, and `web_js_ts_html`.
- The control surface distinguished HOLD/REJECT/REPAIR-style behavior for non-Python surfaces.
- It used status evidence rather than body targets, keeping source/body authority closed.

Interpretation:

- The software maintainer cannot be Python-only.
- Non-Python repair-control should be restored as a structured control objective before language-specific decoder widening.

## Recovered Decoder And Budget Variables

Recovered variables:

- `MAX_DECODER`
- `MAX_ENCODER`
- `FIRST_CODE_STATEMENT_KIND`
- `FIRST_STATEMENT_KIND`
- `LINE_COUNT_BUCKET`
- `SAFE_EXPR_ASSERT_TEMPLATE`
- `MTR_ASSERT_TEMPLATE`
- `EDIT_COMPLETE_BODY`
- `COPY_BODY`
- `VERIFIED_TARGET_BODY`
- `HUNK_EDIT`

Interpretation:

- Decoder rows need first-statement and line-count telemetry.
- Code/output targets should be split into bounded hunk/edit/body categories.
- `MAX_DECODER` and length buckets remain hard budget facts, not learned authority.

## Recovered Native Auxiliary Result

A recent session included a memory of native auxiliary stages 3164-3166:

- Frozen 100M finite heads passed accuracy, balanced, and F1 gates on four tasks.
- Strict NLL exposed overconfidence on at least OP008.
- Reported strict balanced/F1 examples included OP002 around 90.4 percent and OP008 around 85.9 percent.

Interpretation:

- The 100M model has prior evidence of learning finite heads when the objective is clean.
- Future probes need both exact/F1 and strict NLL or calibration gates; accuracy alone is insufficient.

## Recovered Script Names To Consider During Rebuild

High-signal script names recovered from session references:

- `legacy_src/scripts/train_agentkernel_lite_encdec.py`
- `legacy_src/scripts/sample_agentkernel_lite_encdec.py`
- `legacy_src/scripts/build_agentkernel_lite_decoder_repair_curriculum.py`
- `scripts/build_agentkernel_lite_encdec_dataset.py`
- `scripts/run_100m_decoder_software_predictions.py`
- `scripts/train_stage2590_100m_native_controller_head.py`
- `scripts/train_stage1907_100m_action_trajectory_head.py`
- `scripts/train_stage1919_phase_specific_unseen_repo_action_heads.py`
- `scripts/train_stage1918_balanced_unseen_repo_hybrid_action_head.py`
- `scripts/build_stage5970_task_isolated_closed_loop_transition_train_plans.py`
- `scripts/build_stage6324_v27_codegen_dominant_curriculum_manifest.py`
- `scripts/build_stage6717_requested_codegen_matrix_with_behavior_value_overlay.py`
- `scripts/run_stage6718_requested_codegen_pipeline_with_behavior_value_overlay.py`
- `scripts/build_stage6885_requested_codegen_matrix_with_candidate_verifier_overlay.py`
- `scripts/build_stage6862_requested_codegen_matrix_with_target_interface_mlp.py`
- `scripts/run_stage6863_requested_codegen_cli_with_target_interface_mlp.py`
- `scripts/codegraph_core.py`
- `scripts/repo_graph.py`
- `scripts/python_repo_graph.py`
- `scripts/library_repo_graph_export.py`
- `scripts/export_library_repo_graph_hf_dataset.py`
- `scripts/export_repo_code_snippets_hf_dataset.py`
- `scripts/export_paper_universe_hf_dataset.py`

These are references recovered from sessions; they may or may not exist in the current rebuilt workspace. They should be used as reconstruction clues, not execution authority.

## Training Implications

Stage8615 adds missing variables to the recovered training map:

1. Restore behavior-value and candidate-selection objectives.
2. Restore HOLD/REJECT/REPAIR control labels.
3. Restore semantic presentation fields for user intent and maintainer responses.
4. Expand graph families beyond simple call/import/test binding.
5. Rebuild selector/top-k verifier-backed candidate ranking.
6. Keep strict calibration/NLL telemetry for finite heads.
7. Keep all decoder/body/runtime/Gemma authority closed.

## Current Status

Recovered enough to improve the training registry, but not enough to authorize broad mining or training.

Safe next work:

- Mine true `BIND_TEST_TO_SYMBOL` rows for Stage8611.
- Rebuild intent/build strategy miners with semantic presentation fields.
- Rebuild verifier/candidate selector objectives using behavior-value labels.
- Extend repo graph mining with recovered graph families.

Still blocked:

- Broad mining.
- Decoder CE execution.
- Runtime verification execution.
- Body/source emission.
- Gemma/harness/scoring.
- Promotion or controller merge.
