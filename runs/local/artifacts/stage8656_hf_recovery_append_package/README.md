# Recovery 2026-07-04 Append Package

This folder is an append-only recovery package for `PeytonT/100m_swe_research_timeline`. It does not replace the existing Stage1-6158 `train.parquet`; that file already matched the local recovery SHA.

Contents:

- `stage8530_8655_recovery_summaries.jsonl`: reconstructed late-stage summaries after the original HF timeline cutoff.
- `CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md`: current reconstructed software-maintainer spine.
- `reconstructed_stage_registry.json`: local registry snapshot.
- `focused_storage_policy_v1.json`: storage and cleanup safety policy.
- `github_hf_recovery_sources.md`: source recovery notes.
- `recovery_20260704_manifest.json`: this package manifest.

GitHub backup branch: https://github.com/peytontolbert/text-generation-lab/tree/recovery/100m-maintainer-rebuild-20260704

Local `/arxiv` backup archive SHA256: `4b9c6c754d3f1d11a1d1b68b5aa2a25ebe6d5151b6324788edfde5d1ee8a5bbd`

No model execution, decoder CE, runtime, Gemma, harness, scoring, controller merge, or promotion authority is opened by this package.
