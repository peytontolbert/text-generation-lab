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
