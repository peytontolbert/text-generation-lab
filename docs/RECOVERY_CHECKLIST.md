# Recovery Checklist

This checklist is the operational rebuild order. Do not skip ahead to training.

## Phase 0: Freeze Dangerous Actions

- [ ] No model execution.
- [ ] No decoder CE training.
- [ ] No runtime harness.
- [ ] No source/body emission.
- [ ] No Gemma execution.
- [ ] No scoring/harness comparison.
- [ ] No checkpoint export.
- [ ] No cleanup-after-probe execution.
- [ ] No scale-up dataset expansion.

## Phase 1: Safety Foundation

- [x] Recreate `scripts/safe_paths.py`.
- [x] Recreate `scripts/safe_cleanup.py`.
- [x] Recreate `tests/test_safe_cleanup.py`.
- [x] Ensure cleanup refuses `repo_root`.
- [x] Ensure cleanup refuses `/`.
- [x] Ensure cleanup refuses `/data`.
- [x] Ensure cleanup refuses parent of output directory.
- [x] Ensure cleanup refuses symlink traversal outside output directory.
- [x] Ensure cleanup only deletes checkpoint children under output directory.
- [x] Ensure cleanup requires marker file.
- [x] Ensure cleanup requires run id.
- [x] Run cleanup tests. (`pytest -q tests/test_safe_cleanup.py`: 8 passed)

## Phase 2: Registry And Stage Summaries

- [ ] Recreate `scripts/build_stage7678_v27_stage_registry.py`.
- [ ] Reconstruct stage summary schema.
- [ ] Reconstruct authority flags.
- [ ] Recreate `runs/summaries/stage8587_reconstructed_workspace_loss_incident_audit.json`.
- [ ] Reconstruct known Stage7933/8141/8529-8587 summaries from available context.
- [ ] Run registry scan.
- [ ] Verify latest stage and authority counts are unambiguous.

## Phase 3: Dataset Judge And Curriculum Compiler

- [ ] Rebuild deterministic dataset junk/routing ranker.
- [ ] Rebuild shortcut baseline audit utilities.
- [ ] Rebuild loss-mask card generation.
- [ ] Rebuild authority card generation.
- [ ] Rebuild row route outputs:
  - [ ] `KEEP_STRUCTURED`
  - [ ] `KEEP_BOUNDED_DECODER`
  - [ ] `HOLD_LONG_OUTPUT`
  - [ ] `USE_FOR_DENOISE_REPAIR`
  - [ ] `USE_AS_NEGATIVE`
  - [ ] `NEEDS_RETRIEVAL`
  - [ ] `QUARANTINE_LABEL_CONFLICT`
  - [ ] `DROP_DUPLICATE`

## Phase 4: Repo-State Graph

- [ ] Rebuild `repo_state_graph_v1` schema.
- [ ] Use opaque row-local graph IDs.
- [ ] Keep objective metadata outside model input.
- [ ] Rebuild seed manifest.
- [ ] Audit endpoint resolution.
- [ ] Audit label leaks.
- [ ] Audit query-node shortcut.
- [ ] Audit degree-profile shortcut.

## Phase 5: Objective Manifests

- [ ] Rebuild intent-to-build strategy manifest.
- [ ] Rebuild symbol binding manifest.
- [ ] Rebuild edit localization manifest.
- [ ] Rebuild patch operator manifest.
- [ ] Rebuild verifier repair manifest.
- [ ] Rebuild bounded decoder argument manifest.
- [ ] Rebuild bounded decoder CE candidate package.
- [ ] Rebuild denoise repair manifest only after bounded decoder probe is valid.

## Phase 6: Trainer Rebuild

- [ ] Recreate trainer entrypoint only after safety utilities pass.
- [ ] Add hard modes:
  - [ ] `structured_policy_probe`
  - [ ] `repo_graph_probe`
  - [ ] `symbol_binding_probe`
  - [ ] `edit_localization_probe`
  - [ ] `patch_operator_probe`
  - [ ] `verifier_repair_probe`
  - [ ] `bounded_decoder_ce_probe`
  - [ ] `denoise_repair_probe`
- [ ] Add required safety flags.
- [ ] Reject unknown flag combinations.
- [ ] Enforce manifest row caps.
- [ ] Enforce loss masks.
- [ ] Assert no forbidden losses active.
- [ ] Assert no final checkpoint export.
- [ ] Emit telemetry artifacts.
- [ ] Cleanup only through safe cleanup utility.

## Phase 7: Non-Executing Audits

- [ ] Rerun trainer command static audit.
- [ ] Rerun loss-mask reopen audit.
- [ ] Rerun artifact retention cleanup contract audit.
- [ ] Rerun execution manifest audit.
- [ ] Rerun final pre-execution audit.

## Phase 8: Tiny Probe Only After Audit

- [ ] Keep train cap tiny.
- [ ] Keep eval/strict caps tiny.
- [ ] Keep max steps tiny.
- [ ] Require telemetry.
- [ ] Require cleanup proof.
- [ ] Treat output as measurement, not promotion.

## Current Hard Stop

Do not train until:

```text
safe cleanup tests pass
stage registry is rebuilt
loss-mask enforcement audit passes
trainer command surface audit passes
final pre-execution audit passes
```

