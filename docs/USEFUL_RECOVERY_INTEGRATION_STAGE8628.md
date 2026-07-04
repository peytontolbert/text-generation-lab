# Stage8628 Useful Recovery Integration

This stage attaches all currently identified useful `/arxiv` recovery sources into the central graph for the 100M software-maintainer rebuild. It is a reference integration only. It does not authorize training, checkpoint loading, runtime execution, source/body emission, Gemma/harness/scoring, controller merge, or promotion.

## What Was Added

- Useful sources: 43
- Central graph nodes: 1138
- Central graph edges: 1406

## Category Counts

```json
{
  "architecture_recovery": 9,
  "dataset_source": 8,
  "direct_recovery_bundle": 3,
  "model_family_reference": 6,
  "preserved_100m_artifact": 6,
  "reference_repository": 8,
  "runtime_export_reference": 3
}
```

## Target Counts

```json
{
  "bounded_decoder_arguments": 3,
  "central_graph": 1,
  "controlled_maintainer_loop": 5,
  "decoder_history": 2,
  "evidence_retrieval": 1,
  "model_architecture": 1,
  "model_stack": 3,
  "output_repair_denoise": 2,
  "patch_operator": 2,
  "product_harness_integration": 4,
  "repo_state_graph_v1": 7,
  "research_spine": 2,
  "scale_judged_curriculum": 1,
  "structured_policy": 1,
  "trainer_rebuild": 2,
  "training_curriculum": 3,
  "verifier_repair": 3
}
```

## Important Recovery Classes

1. Dedicated recovery bundles: existing reconstructed docs, configs, registries, and session backups.
2. Preserved early 100M checkpoints: stages 968/972, 975/976, 1028, 1029, 1074, 1076.
3. Browser/runtime exports: AgentKernel Lite BitNet/WebGPU/WASM bundles.
4. TOLBERT graph assets: code graph, repo graph, program graph, repo nodes, and code spans.
5. Software-agent references: OpenHands, SWE-agent, Aider, RepairThemAll.
6. Dataset sources: Open-SWE-Traces, SWE-Atlas-QnA, OpenCode*, CodeXGLUE, CodexGLUE.
7. Model-family references: bigram, denoising/diffusion, model optimization, DeepSpeed, LlamaFactory.

## Recovery Rule

These sources are not copied into active training. They are graph-attached references. Any dataset source must pass the dataset judge, shortcut audit, leakage audit, split audit, and loss-mask route card before it can affect gradients. Any code source must be reviewed before being imported into active scripts. Any checkpoint must remain unloaded unless a later explicit checkpoint-inspection stage authorizes it.

## Next Use

Use this graph to rebuild objective builders in this order:

1. intent-to-build neutral masked objective
2. repo-state graph enrichment
3. symbol binding and edit localization
4. patch operator
5. verifier repair
6. bounded decoder argument packaging
7. output repair / denoise dataset

Artifacts:

- `runs/local/artifacts/stage8628_useful_recovery_integration/useful_recovery_sources.json`
- `runs/local/artifacts/stage8628_useful_recovery_integration/central_research_graph_with_useful_recoveries.json`
- `runs/summaries/stage8628_useful_recovery_integration.json`
