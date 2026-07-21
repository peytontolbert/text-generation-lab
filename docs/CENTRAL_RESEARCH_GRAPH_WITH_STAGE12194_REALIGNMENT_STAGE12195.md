# Central Research Graph With Stage12194 Realignment

Stage12195 integrates the Stage12194 current-progress delta into the historical Stage8622 central research graph without mutating the original Stage8622 artifact.

## Integrated Artifact

- Graph: `runs/local/artifacts/stage12195_central_graph_integration/central_research_graph_with_stage12194_realignment.json`
- Nodes: `runs/local/artifacts/stage12195_central_graph_integration/central_research_graph_with_stage12194_realignment_nodes.jsonl`
- Edges: `runs/local/artifacts/stage12195_central_graph_integration/central_research_graph_with_stage12194_realignment_edges.jsonl`
- Summary: `runs/summaries/stage12195_central_graph_integration.json`

## Merge Counts

- Base nodes: 511
- Base edges: 723
- Added nodes: 20
- Added edges: 25
- New nodes: 531
- New edges: 748

## Current Spine State

The old central law remains active:

```text
structured software state
-> safe transition/action policy
-> repo graph grounding
-> bounded decoder
-> verifier-guided repair
-> product/harness integration
```

The refreshed graph now makes the current state explicit:

- Compact selected frontier: Stage11507 + `encoder_option_retrieval_evidence_judgment_head`.
- Hardened compact comparison: Stage11516, 100M `19/19` vs Gemma `3/19`, compact bounded-choice only.
- Standalone transition baseline: Stage11924, `364/640`, below Gemma `386/640`.
- Routed transition candidate: Stage12099, `375/640`, option-permutation stable but route-only and below Gemma.
- Closed-loop task-completion training: blocked by Stage12192 because there are `0` level_3+ episodes and `0` patch-trace episodes.
- Tokenizer: Stage12183 diagnostic lane only; protected 1506-token tokenizer unchanged.

## Next Spine Work

The next central graph lane should be `unbounded_software_task_completion_training`, but it must not start as raw freeform imitation.

It should start as verified episode supervision:

```text
root + task
-> ordered tool/action trace
-> source/test/verifier evidence
-> patch or explicit no-edit decision
-> verifier output
-> state update
-> stop/continue
-> compact projections and structured decoder targets
```

Training remains blocked until the episode floor is met:

- at least 20 level_3+ same-source episodes,
- at least 8 patch-trace episodes,
- at least 10 repositories,
- candidate-action hard-negative floors met,
- no cross-source episode fabrication,
- leak and protected-overlap audits clean.
