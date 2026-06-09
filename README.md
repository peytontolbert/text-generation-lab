# agentkernel-seq2seq-text-lab

PocketPal/Agent Kernel seq2seq text generation, retrieval/intent heads, decoder diagnostics, and text-training research.

This repository is a training and research lab. It is intentionally separate from `agent_kernel_lite`, which remains the runtime/publishing repository.

The first migration pass is non-destructive. `manifests/current_environment.json` records source paths from `/data/agent_kernel_lite` to review and migrate.

## Shared Model Stack

This lab targets `transformer_10`. See [Transformer-10 contract](docs/transformer_10_contract.md).

## Research Docs

- [Full research timeline](docs/full_research_timeline.md) gives the consolidated Stage429-1083 chronology and current claim boundary.
- [Active knowledge compression research](docs/active_knowledge_compression_research.md) tracks the working thesis, detailed stage notes, and artifact index.
- [Stage819-1046 100M bridge research update](docs/stage819_1046_100m_bridge_research_update.md) is the focused 100M bridge note for that range; the full timeline supersedes it for current frontier status.
