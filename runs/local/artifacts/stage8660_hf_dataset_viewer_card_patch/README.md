---
dataset_name: 100m_swe_research_timeline
language:
- en
license: other
task_categories:
- text-generation
- summarization
tags:
- research-timeline
- chronology
- seq2seq
- agentkernel
configs:
- config_name: default
  data_files:
  - split: train
    path: train.parquet
---

# AgentKernel Research Timeline

Chronological export of the AgentKernel / PocketPal research corpus.

This dataset is built from the full unique stage-id union across the repository's stage scripts, stage docs, stage summaries, stage artifacts, and run ledgers. It preserves stage order and bundles source JSON into string columns so the parquet stays easy to inspect in the Hugging Face viewer.

Files:

- `train.parquet`: one row per unique stage id, sorted numerically, with the complete source bundle serialized into string columns.
- `windows.parquet`: short context-window rows for sequence modeling.
- `research_timeline.jsonl`: legacy row dump kept for inspection.
- `research_timeline_windows.jsonl`: legacy context-window dump kept for inspection.
- `manifest.json`: export metadata, coverage counts, and field list.

Primary fields in `train.parquet`:

- `stage`
- `name`
- `created_utc`
- `source_counts`
- `primary_sources`
- `source_text`
- `source_bundle_json`
- `summary_records_json`
- `ledger_records_json`

The corpus is intended as a research archive and chronology modeling dataset, not as a benchmark claim.

## Viewer Configuration Note

The Hugging Face dataset viewer should use the explicit `default` config above, which points only at `train.parquet`. The `recovery_20260704/` folder is an append-only archive package for reconstructed late-stage recovery metadata and should not be inferred as part of the default tabular timeline split.

Current root data files:

- `train.parquet`: Stage1-6158 research timeline rows.
- `manifest.json`: original timeline export metadata.
- `recovery_20260704/`: append-only recovery package for Stage8530-8655 bridge metadata, GitHub backup pointer, storage policy, and reconstructed spine.

The existing `train.parquet` was not replaced during the recovery append. Its LFS SHA256 is `4effdb90e8887d8aac75141c0d0612eaeb4487ea0737560ea1828f0932fa2af1`.

