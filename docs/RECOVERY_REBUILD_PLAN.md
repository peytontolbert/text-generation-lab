# Recovery Rebuild Plan

This document reconstructs the v2.7 100M maintainer recovery plan from available conversation context. It is the working rebuild order after the workspace loss incident.

## Recovery Principle

Rebuild in layers. Do not try to recreate every lost file first.

Priority order:

1. Restore the control plane.
2. Restore the data plane.
3. Restore the training plane.
4. Restore the model plane.

The immediate objective is to prevent another destructive run and preserve the research spine.

## 1. Recovery Foundation

Minimum foundation structure:

```text
README.md
docs/
runs/summaries/
runs/local/artifacts/
scripts/
tests/
legacy_src/scripts/
```

Recovery docs that must exist:

```text
docs/RECOVERY_REBUILD_PLAN.md
docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md
docs/RECOVERY_CHECKLIST.md
runs/summaries/stage8587_reconstructed_workspace_loss_incident_audit.json
```

Next foundation files to rebuild:

```text
scripts/build_stage7678_v27_stage_registry.py
scripts/safe_cleanup.py
tests/test_safe_cleanup.py
```

Do not rebuild the trainer first. Rebuild safety first.

## 2. Control Plane

The control plane decides what is allowed.

Rebuild these concepts:

- stage summary schema
- authority flags
- stage registry
- gate checks
- loss-mask cards
- shortcut audits
- dataset judge
- junk/ranker routes

Every stage summary must carry unambiguous authority flags:

```text
model_execution_authorized_next
decoder_ce_training_authorized_next
runtime_authorized
source_emission_authorized
body_emission_authorized
gemma_execution_authorized_next
harness_execution_authorized_next
scoring_authorized_next
controller_complete_merge_authorized_next
promotion_ready
```

No stage should leave authority ambiguous.

## 3. Research Spine

Rebuild the central spine, not disconnected notes.

Core files:

```text
docs/current_research_spine.md
docs/software_maintainer_model_stack_spine.md
docs/RECOVERY_REBUILD_PLAN.md
```

Active hierarchy:

```text
structured policy
-> repo state graph
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder
-> denoise repair
-> controlled harness
```

This is the architecture. Decoder and runtime remain downstream of the structured control spine.

## 4. Data Plane

Rebuild datasets as typed manifests, not raw text.

Manifest families:

```text
intent_to_build_strategy
repo_state_graph_v1
symbol_binding
edit_localization
patch_operator
verifier_repair
bounded_decoder_arguments
bounded_decoder_ce
denoise_repair
```

Each manifest needs:

```text
rows.jsonl
cell_card.json
loss_card.json
audit.json
baseline_or_shortcut_audit.json
patch_queue.jsonl
summary.json
```

Every row needs:

```text
row_id
split
language_family
input_state
target
loss_mask
authority
source_provenance
anti_cheat_contract
```

## 5. Repo-State Graph Layer

This is the real software-maintainer substrate.

Rebuild `repo_state_graph_v1` around these nodes:

```text
repo
file
module
symbol
function
class
method
import
callsite
test
fixture
config
entrypoint
dependency
external_repo
verifier
failure_log
```

Rebuild these edge types:

```text
contains
defines
imports
exports
calls
instantiates
inherits
test_covers
fixture_used_by
config_controls
entrypoint_invokes
depends_on
external_repo_provides
failure_points_to
patch_edits
verifier_checks
symbol_aliases
language_boundary
```

This graph layer lets the model learn software structure instead of raw code blobs.

## 6. Learning Objectives

Rebuild objectives in this order.

### A. Intent To Build

```text
user intent + constraints
-> USE_WHITELIST_IMPORT | BUILD_ON_TOP | BUILD_FROM_SCRATCH
```

### B. Symbol Binding

```text
call/import/test/failure node
-> target symbol/module/test/null/retrieve
```

### C. Edit Localization

```text
intent + graph + evidence
-> target file/symbol/config/test
```

### D. Patch Operator

```text
localized edit need
-> MODIFY_EXISTING_SYMBOL | ADD_TEST | BUILD_ADAPTER | UPDATE_CONFIG | RETRIEVE | ABSTAIN
```

### E. Verifier Repair

```text
failure log + patch context
-> diagnose / rerun / rollback / repair operator / retrieve more
```

### F. Bounded Decoder Arguments

```text
operator + graph state
-> small bounded argument surface
```

### G. Bounded Decoder CE

Only after all previous structured objectives pass their audits.

```text
bounded input packet
-> short target argument text
```

## 7. Model Architecture

Rebuild as a multi-model system.

Core 100M seq2seq role:

- structured transition predictor
- bounded argument decoder

Core 100M outputs:

- structured heads
- decoder logits
- confidence/OOD heads

Retriever / encoder role:

- find relevant files
- find relevant symbols
- find relevant tests
- find relevant docs

Repo graph / GNN role:

- dependency reasoning
- impact reasoning

SSM/Mamba later role:

- repo-wide compression
- log/history compression
- compact state for transformer planner

Denoiser/diffusion later role:

- iterative repair after verifier failure

Verifier tools role:

- AST checks
- compile checks
- tests
- lint
- typecheck

Do not make the 100M model do everything.

## 8. Trainer Architecture

Rebuild the trainer with hard modes.

Required modes:

```text
structured_policy_probe
repo_graph_probe
symbol_binding_probe
edit_localization_probe
patch_operator_probe
verifier_repair_probe
bounded_decoder_ce_probe
denoise_repair_probe
```

The trainer must reject unknown combinations.

Required safety flags:

```text
--repo-root
--manifest
--mode
--max-train-rows
--max-eval-rows
--max-strict-rows
--max-steps
--decoder-ce-weight
--structured-aux-weight
--denoise-weight
--require-loss-mask-enforcement-audit
--no-final-checkpoint-export
--cleanup-checkpoints-after-probe
--output-dir
```

Cleanup must be guarded. The old unsafe cleanup path must not return.

## 9. Safety Architecture

Create:

```text
scripts/safe_paths.py
scripts/safe_cleanup.py
tests/test_safe_cleanup.py
```

Rules:

- never delete `repo_root`
- never delete `/data`
- never delete `/`
- never delete the parent of `output_dir`
- never follow symlinks outside `output_dir`
- only delete checkpoint children under `output_dir`
- require marker file before cleanup
- require run id before cleanup

No training until these tests pass.

## 10. Telemetry Architecture

Every probe must emit:

```text
loss_by_step.jsonl
eval_loss_by_checkpoint.jsonl
row_field_logits.jsonl
row_field_losses.jsonl
row_token_loss.jsonl
eos_length_audit.json
short_output_probe.json
repetition_probe.json
internal_leak_probe.json
sample_generation_audit.json
module_delta_norms.json
failure_bucket_card.json
cleanup_proof.json
```

Without telemetry, the run is not useful.

## 11. Registry Architecture

Rebuild the stage registry as the source of truth.

It should scan:

```text
runs/summaries/*.json
```

And report:

```text
latest_stage
latest_stage_name
latest_stage_next_best_step
passed_keys
authority_counts
missing_summaries
registry_rows
```

This prevents drift.

## 12. Minimal Rebuild Order

Do this exact order:

1. Restore/recreate safety docs.
2. Rebuild safe path/cleanup utilities.
3. Add cleanup tests.
4. Rebuild stage summary/registry script.
5. Reconstruct Stage7933/8141/8529-8587 summaries as much as possible.
6. Rebuild dataset judge/audit utilities.
7. Rebuild `repo_state_graph_v1` schema and seed manifest.
8. Rebuild objective manifest builders.
9. Rebuild trainer with safe modes.
10. Rebuild tiny model config.
11. Rerun non-executing audits.
12. Only then run a tiny probe.

## 13. What Not To Do

Do not start with:

- training
- scaling to 1M
- free-form codegen
- runtime harness
- Gemma comparison
- checkpoint export
- cleanup after probe

Those are later.

## 14. Architecture In One Line

```text
Safe control plane
-> typed software-state datasets
-> structured transition heads
-> bounded decoder
-> verifier repair loop
-> scale under dataset judge
```

