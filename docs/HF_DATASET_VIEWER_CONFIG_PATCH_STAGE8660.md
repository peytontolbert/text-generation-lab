# Stage8660 HF Dataset Viewer Config Patch

Stage8660 patched the Hugging Face dataset card for `PeytonT/100m_swe_research_timeline` so the default viewer config points explicitly to `train.parquet`. This prevents archive files under `recovery_20260704/` from being inferred as part of the default tabular split.

Remote commit:

`https://huggingface.co/datasets/PeytonT/100m_swe_research_timeline/commit/20a264fc7a5b6d72baed0feab0405ff941b71b12`

The existing root `train.parquet` was not replaced. No delete operation was used. Training/runtime authority remains closed.
