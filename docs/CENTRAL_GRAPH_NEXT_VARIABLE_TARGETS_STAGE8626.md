# Stage8626 Central Graph Variable Targets

This document converts the recovered central research graph into a practical rebuild target map. It is a control-plane note only. It does not authorize training, runtime, decoder CE, Gemma, source/body emission, scoring, harness execution, controller merge, or promotion.

## Current Durable Center

The central graph now exists in:

- `runs/local/artifacts/stage8622_central_research_graph/central_research_graph.json`
- `runs/local/artifacts/stage8624_arxiv_recovery_graph_attachment/central_research_graph_with_arxiv_sources.json`
- `/arxiv/agentkernel_recovery/stage8624_central_graph_recovery/`

The active hierarchy is:

```text
100M software maintainer
-> structured_policy
-> repo_state_graph_v1
-> symbol_binding
-> edit_localization
-> patch_operator
-> verifier_repair
-> bounded_decoder_arguments
-> bounded_decoder_ce_probe
-> output_repair_denoise
-> controlled_maintainer_loop
-> product_harness_integration
```

## Recovered Variable Classes

### Control Plane

Recovered enough to continue rebuilding:

- authority flags
- stage summaries
- registry script
- hard authority closure
- safe cleanup policy
- loss-mask card concept
- telemetry contract concept
- shortcut baseline audits
- counterfactual obligation audits
- dataset judge/ranker route concept

Still needs consolidation:

- one durable stage schema used by every script
- one central graph update hook for every future stage
- one promotion gate file that consumes registry + graph + summaries

### Curriculum Routes

Recovered canonical routes:

- `KEEP_STRUCTURED`
- `KEEP_BOUNDED_DECODER`
- `HOLD_LONG_OUTPUT`
- `USE_FOR_DENOISE_REPAIR`
- `USE_AS_NEGATIVE`
- `NEEDS_RETRIEVAL`
- `QUARANTINE_LABEL_CONFLICT`
- `DROP_DUPLICATE`
- `NEEDS_HUMAN_REVIEW`

Important rule:

```text
route decides which losses may create gradients
```

Current route-to-loss policy is in `configs/software_maintainer/action_feature_registry.json`.

### Dataset Judge Signals

Recovered judge signals:

- `target_over_decoder_budget`
- `long_blob`
- `html_doc_fragment`
- `decoder_target_truncated`
- `raw_internal_token_in_decoder`
- `raw_text_leak_in_structured_objective`
- `short_or_junk_target`
- `degenerate_repetition_target`
- `missing_evidence_but_decode_allowed`
- `budget_bad_but_decode_allowed`
- `action_label_ambiguous`
- `surface_role_conflict`
- `duplicate_semantic_key`
- `split_overlap`
- `shortcut_dominated_feature`
- `teacher_verifier_disagreement`

Still missing:

- one reusable objective-aware junk ranker API
- row-level route card emission for every mined/imported row
- direct graph edge from judge reason -> loss mask -> allowed objective

### Objective Families

Recovered objective families:

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

Implementation status:

| Objective | Status |
|---|---|
| `repo_capability_catalog` | partially executable |
| `repo_state_graph_v1` | partially executable |
| `symbol_binding` | partially executable, patched with test binding rows |
| `intent_to_build_strategy` | recovered as schema/objective, needs builder restored |
| `edit_localization` | recovered as schema/objective, needs builder restored |
| `patch_operator` | recovered as schema/objective, needs builder restored |
| `verifier_repair` | recovered as schema/objective, needs builder restored |
| `bounded_decoder_arguments` | recovered as schema/objective, needs builder restored |
| `bounded_decoder_ce` | package design recovered, execution still closed |
| `output_repair_denoise` | concept recovered, builder not restored |

### Structured Fields

Recovered structured fields:

- `intent_type`
- `target_language`
- `language_group`
- `surface_role`
- `repair_surface`
- `repair_role`
- `build_mode`
- `allowed_import_policy`
- `blocked_import_policy`
- `repo_dependency_policy`
- `file_creation_allowed`
- `modify_existing_allowed`
- `test_required`
- `verification_mode`
- `action_label`
- `action_sequence`
- `file_plan`
- `evidence_state`
- `decode_allowed`
- `decoder_budget_ok`
- `target_length_bucket`
- `retrieve_required`

Hard rule:

```text
retrieve_required is derived unless labels exist.
budget safety is deterministic row fact, not learned authority.
```

### Build Strategy Variables

Recovered build modes:

- `USE_WHITELIST_IMPORT`
- `BUILD_ON_TOP`
- `BUILD_FROM_SCRATCH`

Recovered build actions:

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

Still missing:

- executable neutral masked objective builder for intent-to-build
- compatibility features for allowed imports vs blocked imports
- file plan verifier
- build-mode counterfactual generation

### Repo Graph Variables

Recovered node types:

- `repo`
- `file`
- `module`
- `symbol`
- `function`
- `class`
- `method`
- `import`
- `callsite`
- `test`
- `fixture`
- `config`
- `entrypoint`
- `dependency`
- `external_repo`
- `verifier`
- `failure_log`

Recovered edge types:

- `contains`
- `defines`
- `imports`
- `exports`
- `calls`
- `instantiates`
- `inherits`
- `test_covers`
- `fixture_used_by`
- `config_controls`
- `entrypoint_invokes`
- `depends_on`
- `external_repo_provides`
- `failure_points_to`
- `patch_edits`
- `verifier_checks`
- `symbol_aliases`
- `language_boundary`

Anti-cheat rules:

- graph IDs must be opaque row-local identifiers
- node/edge/graph IDs must not encode labels
- objective metadata must stay outside model input
- query node ID alone must not solve target node ID
- degree profile or edge-type count alone must not solve action or target

### Binding / Localization / Patch / Repair Variables

Recovered binding actions:

- `BIND_CALL_TO_SYMBOL`
- `BIND_IMPORT_TO_MODULE`
- `BIND_TEST_TO_SYMBOL`
- `BIND_FAILURE_TO_SYMBOL`
- `RETRIEVE_MORE`
- `ABSTAIN_UNBOUND`

Recovered edit targets:

- `TARGET_FILE`
- `TARGET_SYMBOL`
- `TARGET_CONFIG`
- `TARGET_TEST`
- `TARGET_ENTRYPOINT`
- `RETRIEVE_MORE`
- `ABSTAIN_UNBOUND`

Recovered patch operators:

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

Recovered verifier-repair actions:

- `DIAGNOSE_FAILURE`
- `RERUN_VERIFIER`
- `LOCALIZE_FAILURE`
- `REPAIR_SYNTAX`
- `REPAIR_ASSERTION`
- `REPAIR_IMPORT`
- `REPAIR_API_CALL`
- `ROLLBACK_OR_ABSTAIN`
- `RETRIEVE_MORE`

Current known blocker:

```text
symbol_binding with test patch solves the BIND_TEST_TO_SYMBOL gap but is still action-imbalanced.
majority_action_baseline_exact = 0.5287, so training remains blocked.
```

### Decoder Variables

Recovered decoder reopen contract:

- `decoder_budget_ok == true`
- `deterministic_budget_ok == true`
- `long_blob == false`
- `html_doc_fragment == false`
- `authority rows == 0`
- no copied target text in model input
- loss mask authorizes `decoder_ce`
- row cap and token cap are enforced
- telemetry artifacts are declared
- no final checkpoint export

Recovered decoder lesson:

```text
zero internal-token leak is not enough.
output must also be contentful, non-short, non-junk, non-repetitive, and budget-clean.
```

Still missing before decoder CE can run:

- trainer CLI/runtime contract patch
- runtime loss-mask enforcement assertions
- no-final-checkpoint-export enforcement
- checkpoint cleanup proof
- final pre-execution audit pass

### Training Telemetry Variables

Required telemetry for future probes:

- `loss_by_step.jsonl`
- `eval_loss_by_checkpoint.jsonl`
- `row_field_logits.jsonl`
- `row_field_losses.jsonl`
- `row_token_loss.jsonl`
- `eos_length_audit.json`
- `short_output_probe.json`
- `repetition_probe.json`
- `internal_leak_probe.json`
- `sample_generation_audit.json`
- `module_delta_norms.json`
- `failure_bucket_card.json`
- `cleanup_proof.json`

Additional interpretability variables:

- per-field margin
- per-field entropy
- top-1/top-2 logit gap
- high-confidence wrong rows
- per-row gradient norm
- module delta norms
- feature ablation attribution
- activation cache/probe hooks

## `/arxiv` Recovery Sources Now Attached

Attached in Stage8624:

- `/arxiv/code/sessions`: 741 session JSONL files, 7,037,033,151 bytes, latest manifest missing count 0
- `/arxiv/preserved_checkpoints_20260609/data/agentkernel-seq2seq-text-lab`: 28 preserved seq2seq records, 4 manifests, 9 checkpoint references
- `/arxiv/datasets`: 42 top-level dataset roots, 28 likely software datasets
- `/arxiv/agentkernel_recovery/stage8624_central_graph_recovery`: longevity docs mirror

Attached in Stage8625:

- 13,833 recoverable `/arxiv` candidates
- 669 architecture-related paths
- 13,139 dataset-source paths
- 19 likely direct recovery paths

High-value Stage8625 roots:

- `/arxiv/TOLBERT_BRAIN`
- `/arxiv/repositories/OpenHands__OpenHands`
- `/arxiv/repositories/OpenHands__software-agent-sdk`
- `/arxiv/repositories/SWE-agent__SWE-agent`
- `/arxiv/repositories/SWE-agent__SWE-ReX`
- `/arxiv/repositories/SWE-agent__mini-swe-agent`
- `/arxiv/repositories/Aider-AI__aider`
- `/arxiv/repositories/CodeXGLUE`
- `/arxiv/repositories/RepairThemAll`
- `/arxiv/repositories/NousResearch__hermes-agent`

## Next Variable Recovery Targets

1. Attach Stage8625 recoverable candidates into the central graph as source nodes.
2. Rebuild objective builders in order:
   - intent-to-build neutral masked builder
   - edit localization builder
   - patch operator builder
   - verifier repair builder
   - bounded decoder argument builder
   - output repair denoise builder
3. Patch symbol-binding imbalance before any training:
   - add or mine more non-test `BIND_*` positives
   - preserve counterfactual obligations
   - rerun majority/query-kind/degree-profile baselines
4. Rebuild trainer command surface only after data objectives are safe:
   - `--manifest`
   - `--mode`
   - row caps
   - loss-mask enforcement audit
   - no final checkpoint export
   - cleanup proof
5. Only after those pass, reconsider the tiny bounded decoder CE pre-execution audit.

## Current Training Status

```text
training authorized: no
decoder CE authorized: no
runtime authorized: no
source/body emission authorized: no
Gemma/harness/scoring authorized: no
controller merge authorized: no
promotion ready: no
```

The rebuild is back to a coherent control spine, but not yet back to model execution.
