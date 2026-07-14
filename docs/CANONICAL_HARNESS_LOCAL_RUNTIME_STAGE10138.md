# Stage10138 Canonical Harness Local Runtime

`scripts/run_stage10138_canonical_harness_local_runtime.py` is the recovered local machine runner for the canonical full-product harness path.

It does four things for each canonical handoff cell:

1. Validates the runtime payload against the Stage10081 handoff bundle.
2. Executes the same locked task-pack payload for:
   - recovered `target_100m`
   - local Ollama Gemma
3. Scores:
   - `tool_trace_spans`
   - `verifier_results`
   - `patch_minimality_or_abstain_scores`
4. Writes the five reserved machine artifacts through the existing Stage10081 adapter.

## Runtime Payload

The runtime payload is JSON with:

- `runtime_payload_version`
- `runs`

Each `runs[]` entry must contain:

- `cell_key`
- `task_pack`
- `hundred_m_backend`
- `gemma_backend`

`task_pack` must keep these fields aligned with the Stage10081 handoff cell:

- `task_pack_id`
- `source_id`
- `lineage_hash`
- `language_family`
- `skill_area`

For Gemma execution, `task_pack.rows[]` must provide:

- `row_id`
- `prompt`
- `expected_label`

For the recovered 100M path, `hundred_m_backend.kind` is currently:

- `target_100m_manifest_probe`

That requires `task_pack.manifest_rows[]` compatible with `legacy_src/scripts/train_agentkernel_lite_encdec.py`.

## Template

Write a payload template with:

```bash
python scripts/run_stage10138_canonical_harness_local_runtime.py --emit-template runs/local/artifacts/stage10138_canonical_harness_local_runtime/canonical_harness_runtime_payload_template.json
```

The template is intentionally placeholder-only. Replace the placeholder rows with the real locked task-pack payload before execution.

## Execution

Dry-run validation:

```bash
python scripts/run_stage10138_canonical_harness_local_runtime.py PAYLOAD.json --dry-run
```

Full local execution and reserved-path writeback:

```bash
python scripts/run_stage10138_canonical_harness_local_runtime.py PAYLOAD.json
```

Skip reserved-path writeback but still execute locally:

```bash
python scripts/run_stage10138_canonical_harness_local_runtime.py PAYLOAD.json --skip-writeback
```

## Current Boundary

This recovers the missing runtime layer.

It does not fabricate the locked task-pack payload itself. The payload still needs the real same-task-pack rows/prompts/manifests that were previously absent from the repo-only scaffold.
