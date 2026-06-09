# Migration Plan

This repo has been scaffolded before switching live training here. The current legacy environment is captured in `manifests/current_environment.json`.

## Phase 1: Review

- Inspect `docs/current_environment_inventory.md`.
- Decide which scripts should be copied versus rewritten.
- Keep checkpoints/artifacts external unless a small fixture is needed.

## Phase 2: Materialize

Dry run:

```bash
python scripts/materialize_selected_files.py
```

Copy selected files into `legacy_src/` after review:

```bash
python scripts/materialize_selected_files.py --execute
```

## Phase 3: Normalize

- Move copied scripts from `legacy_src/scripts/` into `src/` or `scripts/`.
- Convert ad hoc run commands into versioned config files.
- Convert logs into `runs/ledgers/*.jsonl` rows.
- Add smoke tests for one data build, one training dry-run, and one export.

## Phase 4: Switch Training

Training can switch here only after config loading, smoke training, export validation, and promotion back to `agent_kernel_lite` are documented.
