# Recovery Progress: Control Loop Rebuild

This pass rebuilt the non-executing control-loop foundation from recovered session context.

## Rebuilt Utilities

Safety:

```text
scripts/safe_paths.py
scripts/safe_cleanup.py
tests/test_safe_cleanup.py
```

Control plane:

```text
scripts/stage_summary_schema.py
scripts/authority_gate.py
scripts/loss_mask_card.py
scripts/build_stage7678_v27_stage_registry.py
```

Dataset judge/audit:

```text
scripts/shortcut_baseline_audit.py
scripts/structured_dataset_junk_ranker.py
```

Session recovery:

```text
scripts/reconstruct_stage_summaries_from_sessions.py
runs/summaries/reconstructed_from_sessions/stage8530_reconstructed_from_session_index.json ... stage8586_reconstructed_from_session_index.json
```

Config anchors:

```text
configs/schema/stage_summary_schema.json
configs/schema/loss_mask.schema.json
configs/schema/manifest_row.schema.json
configs/schema/repo_state_graph_v1.schema.json
configs/probes/bounded_decoder_ce_probe.json
configs/runtime_profiles/repo_verifier.json
configs/runtime_profiles/system_light.json
configs/runtime_profiles/torch_model.json
configs/model/agentkernel_100m_seq2seq.json
configs/tokenizer/byte_tokenizer.json
```

## Validation

```text
python -m py_compile scripts/*.py: passed
pytest -q: 20 passed
registry rows: 58
registry min/max stage: 8530 / 8587
authority counts: all 0
```

## What This Restores

- Closed-authority stage summary handling.
- Non-destructive stage registry.
- Explicit authority gate.
- Row-level loss-mask validation.
- Deterministic shortcut baseline audit.
- Deterministic objective-aware dataset junk/routing ranker.
- Session-log to closed-authority summary reconstruction.
- Machine-readable schema/config anchors.

## Still Missing

- Original full curriculum compiler implementation.
- Original objective manifest builders and audits for Stage8522-8565.
- Restored/patched 100M trainer entrypoint.
- Bounded decoder CE wrapper/audit scripts Stage8566-8583.
- Exact original stage artifacts/manifests.
- Valid tiny bounded decoder CE execution with retained telemetry.

## Current Rule

No model execution, decoder CE, runtime, Gemma, harness, checkpoint export, or cleanup-after-probe is authorized. The current work is rebuild-only and non-executing.
