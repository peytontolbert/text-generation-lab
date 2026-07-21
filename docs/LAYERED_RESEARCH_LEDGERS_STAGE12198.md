# Layered Research Ledgers Stage12198

Stage12198 adds generated ledgers under the central research graph.

These ledgers are indexes and evidence layers, not direct authority. Every record points back to raw `runs/summaries` files.

## Outputs

- Raw stage index: `runs/local/artifacts/stage12198_layered_research_ledgers/raw_stage_index.jsonl`
- Frontier ledger: `runs/local/artifacts/stage12198_layered_research_ledgers/frontier_ledger.jsonl`
- Failure mechanism ledger: `runs/local/artifacts/stage12198_layered_research_ledgers/failure_mechanism_ledger.jsonl`
- Dataset/source ledger: `runs/local/artifacts/stage12198_layered_research_ledgers/dataset_source_ledger.jsonl`
- Trainer capability ledger: `runs/local/artifacts/stage12198_layered_research_ledgers/trainer_capability_ledger.jsonl`
- Graph with ledger links: `runs/local/artifacts/stage12195_central_graph_integration/central_research_graph_with_stage12198_ledgers.json`
- Summary: `runs/summaries/stage12198_layered_research_ledgers.json`

## Record Counts

- Raw stage index: 3,126
- Frontier ledger: 3,073
- Failure mechanism ledger: 7,505
- Dataset/source ledger: 2,981
- Trainer capability ledger: 2,740

## Interpretation

The first-pass extractors are intentionally broad. They are designed to prevent lost history and support query/triage, not to replace human or deterministic admission decisions.

Training decisions should use these ledgers like this:

1. Check the control spine for current authority and protected gates.
2. Check the frontier ledger for selected baseline, rejected lines, and exact improvement target.
3. Check the dataset/source ledger for admission status, lineage, split, and support-only flags.
4. Check the trainer capability ledger for whether the requested run is contract-only, diagnostic, or executable.
5. Check the failure mechanism ledger for known traps before launching.
6. Verify against raw summaries before any promotion or training request.

## Implementation

Builder:

`scripts/build_stage12198_layered_research_ledgers.py`

The script is deterministic over `runs/summaries/*.json` and updates the graph with ledger nodes.
