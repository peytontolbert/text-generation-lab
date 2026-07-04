# Scripts And Configs Recovery Inventory

This inventory lists the scripts/configs needed to continue the v2.7 100M software-maintainer objective from the reconstructed Stage8586/8587 state.

Status is based on the current recovered workspace plus recovered session context. Missing items must be rebuilt or restored before another probe.

## Hard Rules

- No destructive shell cleanup.
- No model execution until safety, registry, manifest, loss-mask, and final pre-execution audits pass.
- The trainer must not own cleanup directly; it must call the safe cleanup path or leave cleanup disabled.
- Decoder CE remains blocked except for a future tiny bounded probe after all audits are rebuilt.

## Inventory

### safety

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P0 | present | `scripts/safe_paths.py` | Path validation primitives for cleanup; refuses repo root, /, /data, output parent, and symlink escapes. |
| P0 | present | `scripts/safe_cleanup.py` | Only allowed cleanup entrypoint; removes checkpoint children under marked output dirs only. |
| P0 | present | `tests/test_safe_cleanup.py` | Safety regression tests for cleanup path rules. |
| P0 | present | `docs/NO_DESTRUCTIVE_COMMANDS_POLICY.md` | Written policy blocking destructive shell cleanup and broad deletes. |

### control_plane

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P0 | present | `scripts/build_stage7678_v27_stage_registry.py` | Non-destructive reconstructed stage registry over runs/summaries/*.json. |
| P0 | present | `scripts/stage_summary_schema.py` | Canonical stage summary schema and authority flag validation. |
| P0 | present | `scripts/authority_gate.py` | Shared gate checks for model/runtime/body/Gemma/harness/scoring/controller authority. |
| P0 | present | `scripts/loss_mask_card.py` | Loss-mask card builder/validator connecting row routes to enabled losses. |
| P1 | present | `scripts/shortcut_baseline_audit.py` | Generic single-feature/combo shortcut audit utility. |
| P1 | present | `scripts/structured_dataset_junk_ranker.py` | Objective-aware deterministic dataset judge and route/risk scorer. |
| P1 | present | `scripts/curriculum_compiler.py` | Consumes judge routes and emits objective-specific manifests with row-level loss masks. |
| P1 | present | `scripts/reconstruct_stage_summaries_from_sessions.py` | Session-log recovery helper to rebuild JSON stage summaries from archived logs. |

### data_plane

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P1 | missing | `scripts/build_stage8522_v27_intent_to_build_strategy_neutral_objective_manifest.py` | intent_to_build_strategy manifest builder |
| P1 | missing | `scripts/audit_stage8529_v27_intent_to_build_strategy_model_ready_manifest_gate.py` | intent-to-build model-ready/shortcut/authority audit |
| P1 | missing | `scripts/build_stage8536_v27_repo_state_graph_seed_manifest.py` | repo_state_graph_v1 seed manifest builder |
| P1 | missing | `scripts/audit_stage8539_v27_repo_state_graph_seed_audit_after_label_patch.py` | repo graph seed audit with opaque IDs and leak checks |
| P1 | missing | `scripts/build_stage8540_v27_repo_state_graph_symbol_binding_objective_manifest.py` | symbol binding objective builder |
| P1 | missing | `scripts/audit_stage8543_v27_repo_state_graph_symbol_binding_objective_audit_after_patch.py` | symbol binding shortcut/endpoint/authority audit |
| P1 | missing | `scripts/build_stage8544_v27_repo_state_graph_edit_localization_objective_manifest.py` | edit localization objective builder |
| P1 | missing | `scripts/audit_stage8545_v27_repo_state_graph_edit_localization_objective_audit.py` | edit localization audit |
| P1 | missing | `scripts/build_stage8546_v27_repo_state_graph_patch_operator_objective_manifest.py` | patch operator objective builder |
| P1 | missing | `scripts/audit_stage8547_v27_repo_state_graph_patch_operator_objective_audit.py` | patch operator audit |
| P1 | missing | `scripts/build_stage8548_v27_repo_state_graph_verifier_repair_objective_manifest.py` | verifier repair objective builder |
| P1 | missing | `scripts/audit_stage8549_v27_repo_state_graph_verifier_repair_objective_audit.py` | verifier repair audit |
| P1 | missing | `scripts/build_stage8550_v27_repo_state_graph_bounded_decoder_argument_manifest.py` | bounded decoder argument manifest builder |
| P1 | missing | `scripts/audit_stage8553_v27_bounded_decoder_argument_audit_after_target_patch.py` | bounded decoder argument audit after target patch |
| P1 | present | `scripts/build_stage8564_v27_bounded_decoder_ce_candidate_package_design.py` | Builds bounded decoder CE candidate package rows from bounded argument rows or reconstructed seed contract. |
| P1 | present | `scripts/audit_stage8565_v27_bounded_decoder_ce_candidate_package_design_audit.py` | Audits candidate package balance, target-reference-only policy, caps, and closed authority. |

### training_plane

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P0 | present scaffold | `legacy_src/scripts/train_agentkernel_lite_encdec.py` | Closed-boundary trainer command surface; validates bounded decoder CE probe contracts and refuses model execution. |
| P1 | present | `scripts/build_stage8566_v27_bounded_decoder_ce_probe_wrapper_design.py` | Non-executing bounded decoder CE wrapper design builder. |
| P1 | present | `scripts/audit_stage8567_v27_bounded_decoder_ce_probe_wrapper_design_audit.py` | Static wrapper design audit; validates required flags and trainer help without running training. |
| P1 | present | `scripts/build_stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design.py` | Builds decoder-ce-only loss-mask rows from audited bounded decoder candidates. |
| P1 | present | `scripts/audit_stage8569_v27_bounded_decoder_ce_loss_mask_reopen_design_audit.py` | Audits decoder-ce-only rows for caps, authority, target length, and copied-target leakage. |
| P1 | missing | `scripts/build_stage8570_v27_bounded_decoder_ce_trainer_command_static_design.py` | trainer command static design |
| P1 | missing | `scripts/audit_stage8571_v27_bounded_decoder_ce_trainer_command_static_audit.py` | trainer command static audit |
| P1 | missing | `scripts/build_stage8572_v27_bounded_decoder_ce_artifact_retention_cleanup_contract.py` | artifact retention/cleanup contract builder |
| P1 | missing | `scripts/audit_stage8573_v27_bounded_decoder_ce_artifact_retention_cleanup_contract_audit.py` | cleanup contract audit |
| P1 | missing | `scripts/build_stage8578_v27_bounded_decoder_ce_tiny_probe_execution_manifest.py` | tiny probe execution manifest builder |
| P1 | missing | `scripts/audit_stage8579_v27_bounded_decoder_ce_tiny_probe_execution_manifest_audit.py` | tiny probe manifest audit |
| P1 | present | `scripts/audit_stage8583_v27_bounded_decoder_ce_patched_final_pre_execution_audit.py` | Non-executing final pre-execution audit for bounded decoder CE probe. |

### config_plane

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P1 | present | `configs/runtime_profiles/repo_verifier.json` | Runtime profile recovered in registry list; must remain non-executing until authorized. |
| P1 | present | `configs/runtime_profiles/system_light.json` | System light runtime/profile config recovered in registry list. |
| P1 | present | `configs/runtime_profiles/torch_model.json` | Torch model runtime/profile config recovered in registry list. |
| P1 | present | `configs/model/agentkernel_100m_seq2seq.json` | 100M seq2seq model config for structured heads and bounded decoder. |
| P1 | present | `configs/tokenizer/byte_tokenizer.json` | Byte-level tokenizer config used in decoder probes; needed for target budget checks. |
| P1 | present | `configs/schema/stage_summary_schema.json` | Machine-readable stage summary and authority schema. |
| P1 | present | `configs/schema/repo_state_graph_v1.schema.json` | Node/edge schema for repo_state_graph_v1. |
| P1 | present | `configs/schema/loss_mask.schema.json` | Loss-mask schema for row-level gradient routing. |
| P1 | present | `configs/schema/manifest_row.schema.json` | Canonical manifest row schema. |
| P1 | present | `configs/probes/bounded_decoder_ce_probe.json` | Tiny bounded decoder CE probe caps/config. |

### external_recovery_source

| Priority | Status | Path | Purpose |
|---|---|---|---|
| P1 | exists | `/data/agentkernel/scripts/train_agentkernel_lite_encdec.py` | possible external recovery source for trainer |
| P1 | exists | `/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py` | possible external recovery source for trainer |
| P1 | exists | `/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py` | possible external recovery source for trainer |

## Immediate Rebuild Order

1. Keep safety utilities/tests passing.
2. Rebuild `stage_summary_schema.py`, `authority_gate.py`, and `loss_mask_card.py`.
3. Reconstruct Stage8535-8586 JSON summaries from session index where possible.
4. Rebuild dataset judge and shortcut audit utilities.
5. Rebuild repo graph/objective manifest builders in stage order.
6. Restore trainer entrypoint only after cleanup safety is enforced.
7. Rebuild bounded decoder CE wrapper/audit scripts.
8. Rerun non-executing audits before any model execution.

## External Trainer Candidate Review

These files exist outside the recovered workspace and can help restore `legacy_src/scripts/train_agentkernel_lite_encdec.py`, but none should be copied blindly. The recovered trainer must be adapted to the safe probe contract and safe cleanup utilities.

| Path | Lines | SHA256 | Key gaps |
|---|---:|---|---|
| `/data/agentkernel/scripts/train_agentkernel_lite_encdec.py` | 2227 | `58091c0f0a5492ff88e061a520da207d14282d422d2349de1b796a2d5bc189bd` | --manifest, --mode, --decoder-ce-weight, --structured-aux-weight, --denoise-weight, --max-strict-rows, --require-loss-mask-enforcement-audit, --no-final-checkpoint-export, --cleanup-checkpoints-after-probe, --skip-final-model-save, --max-train-rows, --max-eval-rows |
| `/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py` | 4522 | `ec4c5a06ad2b16291e8ef39c35710bafd326b293b9e39602c451d2e1a4128afe` | --manifest, --mode, --decoder-ce-weight, --structured-aux-weight, --denoise-weight, --max-strict-rows, --require-loss-mask-enforcement-audit, --no-final-checkpoint-export, --cleanup-checkpoints-after-probe, --skip-final-model-save, --max-train-rows, --max-eval-rows |
| `/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py` | 3564 | `71ea00f56ef55d7922de43f40f5a5344e16d9796d382a55e5be211ae7f3f1176` | --manifest, --mode, --decoder-ce-weight, --structured-aux-weight, --denoise-weight, --max-strict-rows, --require-loss-mask-enforcement-audit, --no-final-checkpoint-export, --cleanup-checkpoints-after-probe, --skip-final-model-save, --max-train-rows, --max-eval-rows |

Required restored trainer behavior:

- support `--mode bounded_decoder_ce_probe` as a hard mode
- accept audited manifest path and strict/train/eval row caps
- enforce loss masks at runtime
- set decoder CE / structured aux / denoise weights explicitly
- prevent final checkpoint export
- never perform broad cleanup; use `scripts/safe_cleanup.py` or leave cleanup disabled
- emit required telemetry before any execution can be considered useful

## External Recovery Sources Added

Recovered read-only source snapshots are now stored under `runs/local/artifacts/remote_recovery/`.

### GitHub: peytontolbert/text-generation-lab

Source URL: `https://github.com/peytontolbert/text-generation-lab`

Snapshot:

- HEAD SHA: `4f3a96ced98926a3820397f3ee519ea39cc0e4d3`
- recursive tree: `runs/local/artifacts/remote_recovery/github_text_generation_lab/tree.json`
- selected raw files: `runs/local/artifacts/remote_recovery/github_text_generation_lab/files/`

Useful recovered files:

- `legacy_src/scripts/train_agentkernel_lite_encdec.py`
- `legacy_src/scripts/build_agentkernel_lite_encdec_dataset.py`
- `legacy_src/scripts/build_agentkernel_lite_decoder_repair_curriculum.py`
- `legacy_src/scripts/build_agentkernel_lite_research_retrieval_curriculum.py`
- `legacy_src/scripts/sample_agentkernel_lite_encdec.py`
- `docs/full_research_timeline.md`
- `docs/current_environment_inventory.md`
- `docs/repository_contract.md`
- `manifests/current_environment.json`
- `runs/ledgers/pocketpal_seq2seq_runs.jsonl`

Important limitation: the fetched GitHub trainer is legacy. It has zero occurrences of the Stage8580/8586 bounded decoder CE probe flags (`--manifest`, `--mode`, `--decoder-ce-weight`, `--require-loss-mask-enforcement-audit`, `--no-final-checkpoint-export`, `--cleanup-checkpoints-after-probe`, etc.). It can be used as a reference base, but it must not be restored as the active trainer without the safety surface patch.

### Hugging Face: PeytonT/100m_swe_research_timeline

Source URL: `https://huggingface.co/datasets/PeytonT/100m_swe_research_timeline`

Snapshot:

- dataset SHA: `a50a0f26fd2538dd67b2157c41484b4733dfdfae`
- manifest: `runs/local/artifacts/remote_recovery/hf_100m_swe_research_timeline/files/manifest.json`
- README: `runs/local/artifacts/remote_recovery/hf_100m_swe_research_timeline/files/README.md`

Manifest facts:

- stage_count: `5615`
- stage_min: `1`
- stage_max: `6158`
- summary_source_count: `5147`
- source_kind_counts: `artifact_file=60246`, `doc=73`, `script=4140`, `summary=5147`

Important limitation: Hugging Face is an early/mid timeline archive through Stage6158. It cannot recover the Stage8400-8587 structured-maintainer and bounded-decoder branch. Use local session logs as source of truth for late-stage recovery.

Detailed review: `docs/GITHUB_HF_RECOVERY_SOURCES.md`.



## Stage8588 Trainer Scaffold Recovery

`legacy_src/scripts/train_agentkernel_lite_encdec.py` is now present as a non-executing contract scaffold. It supports the Stage8580/8586 flags, validates bounded decoder CE probe manifests, enforces loss-mask/cap/authority checks, emits placeholder telemetry, and refuses model execution outside `--contract-only` audit mode.

This does not restore actual training. It only restores the command/runtime safety surface needed to rebuild wrapper and pre-execution audits.

Summary: `runs/summaries/stage8588_reconstructed_bounded_decoder_ce_trainer_contract_scaffold.json`.


## Stage8589 Wrapper Rebuild

Rebuilt Stage8566/8567 bounded decoder CE wrapper design and audit scripts:

- `scripts/build_stage8566_v27_bounded_decoder_ce_probe_wrapper_design.py`
- `scripts/audit_stage8567_v27_bounded_decoder_ce_probe_wrapper_design_audit.py`

Generated artifacts:

- `runs/local/artifacts/rebuilt_stage8566_bounded_decoder_ce_probe_wrapper_design.json`
- `runs/local/artifacts/rebuilt_stage8567_bounded_decoder_ce_probe_wrapper_design_audit.json`

The rebuilt wrapper is non-executing and includes `--contract-only`. The audit passed with all required flags present, forbidden flags absent, trainer help support present, authority closed, and output path under repo root.

Summary: `runs/summaries/stage8589_reconstructed_bounded_decoder_ce_wrapper_design_audit.json`.


## Stage8590 Loss-Mask Reopen Rebuild

Rebuilt Stage8568/8569 bounded decoder CE loss-mask reopen scripts:

- `scripts/build_stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design.py`
- `scripts/audit_stage8569_v27_bounded_decoder_ce_loss_mask_reopen_design_audit.py`

The scripts are tested against toy candidates and enforce:

- `KEEP_BOUNDED_DECODER` / decode-allowed route
- deterministic decoder budget OK
- target token length under cap
- no copied target text in model input
- closed authority
- decoder-CE-only loss masks
- train/eval/strict caps

The original Stage8568 candidate rows are not recovered yet. Do not treat this as a real probe-ready manifest until candidate rows are restored or rebuilt and audited.

Summary: `runs/summaries/stage8590_reconstructed_bounded_decoder_ce_loss_mask_reopen_scripts.json`.


## Stage8592 Candidate Package Rebuild

Rebuilt candidate package scripts and generated reconstructed replacement row bodies from the recovered Stage8564/8568 contract.

Artifacts:

- `runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_candidate_package/rows.jsonl`
- `runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_candidate_package/audit.json`
- `runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_loss_mask/rows.jsonl`
- `runs/local/artifacts/stage8592_reconstructed_bounded_decoder_ce_loss_mask/audit.json`

Known status:

- candidate rows: 96
- selected loss-mask rows: 64
- decoder CE only: true
- authority rows: 0
- over-cap rows: 0
- copied target text rows: 0

These rows are reconstructed replacement rows, not original recovered artifacts. They are suitable for non-executing pipeline/audit restoration. Do not use them for capability claims.

Summary: `runs/summaries/stage8592_reconstructed_bounded_decoder_ce_candidate_and_loss_mask_package.json`.


## Stage8594 Final Pre-Execution Audit Rebuild

Rebuilt and ran the final pre-execution audit against reconstructed bounded decoder CE loss-mask rows.

Artifact:

- `runs/local/artifacts/stage8594_reconstructed_final_pre_execution_audit.json`

Result:

- passed: true
- manifest rows: 64
- unsafe loss rows: 0
- authority rows: 0
- over-cap rows: 0
- trainer help required flags: present
- wrapper command: contract-only
- execution authorized: false

Summary: `runs/summaries/stage8594_reconstructed_bounded_decoder_ce_final_pre_execution_audit.json`.

- `scripts/audit_curriculum_compiler_outputs.py`: audits compiler output manifests for objective/loss/authority consistency.

- `scripts/build_training_plan.py`: builds non-executing training plan contracts.
- `scripts/audit_training_plan.py`: audits training plans for manifests, tiny caps, closed authority, and no runtime loss.


## Stage8595-8596 Training Compiler Recovery

Restored the central curriculum compiler and non-executing training-plan contracts. Artifacts live under `runs/local/artifacts/stage8595_reconstructed_curriculum_compiler/` and `runs/local/artifacts/stage8596_reconstructed_training_plan/`. Execution remains closed.

- `scripts/training_runtime_contract.py`: builds non-executing 100M training runtime contracts.
- `scripts/audit_training_runtime_contract.py`: audits runtime contract components/telemetry/authority/checkpoint policy.
- `scripts/training_telemetry.py`: emits required telemetry artifact surface without model execution.


## Stage8597 Training Runtime Contract Recovery

Restored the training runtime contract and telemetry surface. Forward/backward and optimizer execution remain explicitly not restored. Artifacts live under `runs/local/artifacts/stage8597_reconstructed_training_runtime_contract/`.

- `legacy_src/agentkernel_lite/modeling.py`: recovered importable seq2seq model scaffold with structured heads and decoder CE helper.
- `legacy_src/agentkernel_lite/training_data.py`: byte tokenizer and manifest batch builder.
- `scripts/audit_model_implementation.py`: no-grad forward/loss implementation audit.


## Stage8598 Model Implementation Smoke Recovery

Restored model/batching modules and verified no-grad forward/loss smoke in `/home/peyton/miniconda3/envs/code_assist_runtime/bin/python`. Backward/optimizer/checkpoint execution remains not restored and not authorized.

- `legacy_src/agentkernel_lite/training_loop.py`: gated tiny bounded decoder CE training loop with telemetry and no checkpoint export.
- `scripts/audit_trainer_execution_implementation.py`: static/import audit for gated trainer execution implementation.


## Stage8599 Gated Trainer Execution Implementation

Restored the tiny bounded decoder CE training-loop implementation and wired it behind `--execution-authorized-for-recovery-probe`. Default trainer invocation remains non-executing and refuses without the gate. No model training was run in this stage.
