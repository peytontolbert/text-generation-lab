# Repository Contract

Model family: `seq2seq_text`

This lab depends on `agentkernel-model-core` for shared schemas and the `transformer_10` compatibility contract. Modality-specific experiments belong here; runtime integration belongs in `agent_kernel_lite`.

## Promotion requirements

- export manifest following `agentkernel-model-core/schemas/export_manifest.schema.json`
- model config and checkpoint or quantized bundle
- eval summary with pass/fail verdict
- run ledger row documenting hypothesis, dataset, base checkpoint, and result

Large checkpoints and datasets are not committed by default. Commit manifests, configs, scripts, diagnostics summaries, and model cards.
