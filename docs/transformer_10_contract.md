# Seq2Seq Text Transformer-10 Use

The text lab uses `transformer_10` as the sequence backbone while keeping tokenization, retrieval/intent heads, decoder training, latent auxiliary losses, and text runtime packaging local to this repository.

## Contract Source

Shared compatibility rules live in `/data/agentkernel-model-core/docs/transformer_10_contract.md` and `/data/agentkernel-model-core/schemas/transformer_10_contract.schema.json`.

This lab must record `model_stack: transformer_10` and `model_family: seq2seq_text` in promoted export manifests. Architecture changes are allowed, but every adapter, conditioning stream, objective term, and runtime target should be declared rather than inferred from script names.

## Local Responsibilities

- Keep training scripts, curriculum definitions, diagnostics, and research notes in this lab.
- Keep source inventories and migration manifests current while extracting code from `/data/agent_kernel_lite`.
- Do not commit heavy checkpoints, raw generated media, or temporary training outputs by default.
- Promote only bundles that have an eval summary, run ledger row, and export manifest.
