# Stage8663 HF Multi-Config Viewer Patch

Stage8663 updated `PeytonT/100m_swe_research_timeline` to expose two explicit Hugging Face viewer configs:

- `timeline_stage1_6158`: default config, backed by root `train.parquet`.
- `recovery_stage8530_8662`: late recovery bridge, backed by `recovery_20260704/stage8530_8662_recovery_summaries.jsonl`.

No second project-local `train.parquet` needed upload. The other discovered `/arxiv/**/train.parquet` files are different corpora, not additional copies of this timeline dataset.

Remote commit:

`https://huggingface.co/datasets/PeytonT/100m_swe_research_timeline/commit/1a89aa8a0267fad894f926cf38c213dc12a2bd5a`

No delete operation was used. Training/runtime authority remains closed.
