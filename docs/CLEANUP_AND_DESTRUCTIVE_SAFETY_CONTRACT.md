# Cleanup And Destructive Safety Contract

## Purpose

This repository has exactly one sanctioned cleanup entrypoint for probe artifacts:

- `scripts/safe_cleanup.py`

Cleanup and destructive filesystem behavior must remain centralized. No ad hoc deletion logic is allowed in trainers, wrappers, or stage scripts.

## Hard Rules

1. Never delete `/`.
2. Never delete `/data`.
3. Never delete `/arxiv`.
4. Never delete any descendant of `/arxiv`.
5. Never delete `repo_root`.
6. Never delete `repo_root.parent`.
7. Never delete `output_dir` itself.
8. Never delete `output_dir.parent`.
9. Never follow symlinks outside the bounded probe output subtree.
10. Only delete checkpoint children under the exact probe `output_dir`.
11. Require the `.agentkernel_probe_output` marker file.
12. Require the matching `run_id` inside the marker file.
13. Cleanup must support `--dry-run`.
14. Trainer and probe code must call only `safe_cleanup_checkpoints(...)` for checkpoint cleanup.
15. No stage script, trainer, or helper may freehand `rm`, `shutil.rmtree(repo_root)`, `shutil.rmtree(output_dir)`, or equivalent destructive patterns.

## Enforcement Points

- `scripts/safe_paths.py`
  - central path validation and cleanup planning
- `scripts/safe_cleanup.py`
  - only public cleanup entrypoint
- `tests/test_safe_cleanup.py`
  - negative tests for forbidden roots and path escapes
- `scripts/manifest_path_validator.py`
  - blocks `/arxiv` and arbitrary `/data` manifest inputs outside the repo
- `legacy_src/scripts/train_agentkernel_lite_encdec.py`
  - may only use `safe_cleanup_checkpoints(...)`

## Model/Trainer Safety Policy

The model and trainer must not be allowed to perform destructive filesystem actions directly.

Destructive behavior must remain blocked unless all of the following are true:

- explicit user authorization exists
- the path is validated against central safe path rules
- the action is scoped under a bounded probe output directory
- the action is represented as cleanup of temporary checkpoint children only
- the action is auditable through emitted cleanup telemetry

The maintainer model should learn software maintenance transitions, not destructive filesystem authority.
