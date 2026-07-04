# Session Recovery Feature Gap Audit

This audit records what was recovered from `/home/peyton/.codex/sessions` and what is still missing after the workspace rebuild.

## Recovery Sources

- Session root checked: `/home/peyton/.codex/sessions`
- July session directory present: no
- July session files found: 0
- Relevant session recovery index: `runs/local/artifacts/session_recovery/stage8530_8589_session_hit_index.jsonl`
- Session hits indexed: 298
- Stages with indexed hits: 58
- Reconstructed closed-authority side summaries written: 57
- Side summary directory: `runs/summaries/reconstructed_from_sessions`

The side summaries are intentionally not top-level active registry summaries. They preserve recoverable facts while keeping all authority closed.

## Current Active Frontier

- Active top-level registry latest stage: `8602`
- Latest stage name: `stage8602_reconstructed_arxiv_repo_capability_graph_seed_audit`
- Active registry rows: 73
- Runtime/body/source/Gemma/harness/scoring/controller authority: closed
- Decoder CE authority: closed
- Model execution authority: closed

Stage8602 is a useful source-substrate stage, not a training stage. It produced repo capability and repo graph seed rows from `/arxiv/repositories`, with zero decoder rows and zero model-ready training rows.

## What Is Recovered Conceptually

The following concepts/actions are present in docs or config:

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
- build modes: `USE_WHITELIST_IMPORT`, `BUILD_ON_TOP`, `BUILD_FROM_SCRATCH`
- dataset routes: `KEEP_STRUCTURED`, `KEEP_BOUNDED_DECODER`, `HOLD_LONG_OUTPUT`, `USE_FOR_DENOISE_REPAIR`, `USE_AS_NEGATIVE`, `NEEDS_RETRIEVAL`, `QUARANTINE_LABEL_CONFLICT`, `DROP_DUPLICATE`, `NEEDS_HUMAN_REVIEW`

So the missing problem is not the high-level architecture. The missing problem is executable, objective-specific curriculum continuity.

## Still Missing As Executable Scripts

These P1 scripts are still absent and should be rebuilt or restored before another probe:

- `scripts/build_stage8522_v27_intent_to_build_strategy_neutral_objective_manifest.py`
- `scripts/audit_stage8529_v27_intent_to_build_strategy_model_ready_manifest_gate.py`
- `scripts/build_stage8536_v27_repo_state_graph_seed_manifest.py`
- `scripts/audit_stage8539_v27_repo_state_graph_seed_audit_after_label_patch.py`
- `scripts/build_stage8540_v27_repo_state_graph_symbol_binding_objective_manifest.py`
- `scripts/audit_stage8543_v27_repo_state_graph_symbol_binding_objective_audit_after_patch.py`
- `scripts/build_stage8544_v27_repo_state_graph_edit_localization_objective_manifest.py`
- `scripts/audit_stage8545_v27_repo_state_graph_edit_localization_objective_audit.py`
- `scripts/build_stage8546_v27_repo_state_graph_patch_operator_objective_manifest.py`
- `scripts/audit_stage8547_v27_repo_state_graph_patch_operator_objective_audit.py`
- `scripts/build_stage8548_v27_repo_state_graph_verifier_repair_objective_manifest.py`
- `scripts/audit_stage8549_v27_repo_state_graph_verifier_repair_objective_audit.py`
- `scripts/build_stage8550_v27_repo_state_graph_bounded_decoder_argument_manifest.py`
- `scripts/audit_stage8553_v27_bounded_decoder_argument_audit_after_target_patch.py`
- `scripts/build_stage8570_v27_bounded_decoder_ce_trainer_command_static_design.py`
- `scripts/audit_stage8571_v27_bounded_decoder_ce_trainer_command_static_audit.py`
- `scripts/build_stage8572_v27_bounded_decoder_ce_artifact_retention_cleanup_contract.py`
- `scripts/audit_stage8573_v27_bounded_decoder_ce_artifact_retention_cleanup_contract_audit.py`
- `scripts/build_stage8578_v27_bounded_decoder_ce_tiny_probe_execution_manifest.py`
- `scripts/audit_stage8579_v27_bounded_decoder_ce_tiny_probe_execution_manifest_audit.py`

## Current Generic Utilities Are Not Enough

Recovered generic utilities are useful:

- `scripts/structured_dataset_junk_ranker.py`
- `scripts/curriculum_compiler.py`
- `scripts/shortcut_baseline_audit.py`
- `scripts/loss_mask_card.py`
- `scripts/authority_gate.py`

But they do not replace the missing stage-specific builders/audits because they do not reconstruct:

- symbol/import/test binding candidates
- edit-localization targets
- patch-operator labels
- verifier-repair labels
- bounded-decoder argument rows
- objective-specific shortcut baselines
- objective-specific row coverage cards

## Correct Rebuild Order

Use the Stage8600/8601/8602 `/arxiv` substrate, but rebuild the transition curriculum in this order:

1. Restore or recreate the repo graph seed builder/audit as an executable stage pair.
2. Extract symbol/import/test binding candidates with opaque IDs and shortcut baselines.
3. Build edit-localization rows from binding candidates.
4. Build patch-operator rows from localized targets.
5. Build verifier-repair rows from failure/verifier evidence.
6. Build bounded-decoder argument rows from already-passed structured rows.
7. Only then regenerate bounded decoder CE candidate/loss-mask rows.
8. Only then consider a tiny bounded decoder CE execution gate.

## Hard Stop

Do not use Stage8602 graph seed rows directly as model training rows. They are closed-authority seed/catalog rows. Training rows require objective-specific manifests, loss masks, leakage checks, shortcut baselines, split coverage, and regression cards.

