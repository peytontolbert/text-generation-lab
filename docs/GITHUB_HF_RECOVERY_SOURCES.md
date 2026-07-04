# GitHub and Hugging Face Recovery Sources

This note records what was recovered from the two external sources supplied after the workspace-loss incident:

- GitHub: `https://github.com/peytontolbert/text-generation-lab`
- Hugging Face: `https://huggingface.co/datasets/PeytonT/100m_swe_research_timeline`

All use here is read-only recovery. These sources are evidence and legacy bases, not authorization to run training, runtime, Gemma, hidden scoring, harnesses, or checkpoint export.

## Recovery Boundary

The late Stage8500+ branch is best recovered from local Codex session logs, not these external sources.

The external sources are still important:

- GitHub restores older repository structure, legacy trainer/dataset builders, ledgers, environment inventory, and research docs.
- Hugging Face restores a serialized early/mid research timeline through Stage6158.
- Neither source should overwrite rebuilt safety/control files without review.
- Remote trainer code must be treated as legacy until patched to the Stage8580/8586 safety contract.

## GitHub Snapshot

Repository: `peytontolbert/text-generation-lab`

Default branch: `main`

HEAD SHA: `4f3a96ced98926a3820397f3ee519ea39cc0e4d3`

Tree file count: `493`

Tree truncated: `False`

Fetched files were copied under:

`runs/local/artifacts/remote_recovery/github_text_generation_lab/files/`

Important fetched files:

| Path | Bytes | Use |
| --- | ---: | --- |
| `README.md` | 1105 | repository identity and lab boundary |
| `pyproject.toml` | 249 | legacy packaging/dependency hints |
| `docs/full_research_timeline.md` | 20654 | early research chronology |
| `docs/current_environment_inventory.md` | 7228 | environment/source inventory |
| `docs/repository_contract.md` | 682 | promotion/runtime separation contract |
| `manifests/current_environment.json` | 115091 | source migration map |
| `legacy_src/scripts/train_agentkernel_lite_encdec.py` | 292386 | legacy trainer base only; not Stage8580-ready |
| `legacy_src/scripts/build_agentkernel_lite_encdec_dataset.py` | 105513 | legacy seq2seq dataset builder recovery |
| `legacy_src/scripts/build_agentkernel_lite_decoder_repair_curriculum.py` | 22695 | legacy decoder repair curriculum builder recovery |
| `legacy_src/scripts/build_agentkernel_lite_research_retrieval_curriculum.py` | 26853 | legacy retrieval/research curriculum builder recovery |
| `legacy_src/scripts/sample_agentkernel_lite_encdec.py` | 15675 | legacy sampler/reference inference surface |
| `runs/ledgers/pocketpal_seq2seq_runs.jsonl` | 779197 | run ledger recovery evidence |


## Legacy Trainer Finding

The fetched GitHub trainer is substantial but older:

- path: `runs/local/artifacts/remote_recovery/github_text_generation_lab/files/legacy_src/scripts/train_agentkernel_lite_encdec.py`
- lines: `6180`

Stage8580 failed because the active trainer did not support the audited bounded decoder CE probe command surface. The fetched GitHub trainer also does **not** contain that surface:

| Required Stage8580/8586 flag | Occurrences in GitHub trainer |
| --- | ---: |
| `--manifest` | 0 |
| `--mode` | 0 |
| `--decoder-ce-weight` | 0 |
| `--denoise-weight` | 0 |
| `--structured-aux-weight` | 0 |
| `--max-strict-rows` | 0 |
| `--require-loss-mask-enforcement-audit` | 0 |
| `--no-final-checkpoint-export` | 0 |
| `--cleanup-checkpoints-after-probe` | 0 |
| `--skip-final-model-save` | 0 |


Therefore this trainer can help rebuild older model/data logic, but it must not be copied directly into active execution. The active trainer still needs a deliberate patch that adds the bounded-probe safety flags and runtime assertions:

- `--manifest`
- `--mode bounded_decoder_ce_probe`
- `--decoder-ce-weight`
- `--structured-aux-weight`
- `--denoise-weight`
- `--max-strict-rows`
- `--require-loss-mask-enforcement-audit`
- `--no-final-checkpoint-export`
- `--cleanup-checkpoints-after-probe`
- `--skip-final-model-save`

Runtime assertions required before any execution:

- only audited manifest rows load
- row caps enforced
- loss masks enforced
- only decoder CE contributes in bounded decoder CE probe mode
- no source/body/runtime/Gemma/harness/scoring path active
- no final checkpoint export
- cleanup cannot delete repo root, parent dirs, or symlink escapes

## Hugging Face Snapshot

Dataset id: `PeytonT/100m_swe_research_timeline`

Dataset SHA: `a50a0f26fd2538dd67b2157c41484b4733dfdfae`

Last modified: `2026-06-27T19:01:14.000Z`

Fetched files were copied under:

`runs/local/artifacts/remote_recovery/hf_100m_swe_research_timeline/files/`

Manifest facts:

| Field | Value |
| --- | --- |
| artifact_kind | `agentkernel_lite_research_timeline_export` |
| dataset_name | `100m_swe_research_timeline` |
| created_utc | `2026-06-27T18:59:53.810439+00:00` |
| stage_count | `5615` |
| stage_min | `1` |
| stage_max | `6158` |
| summary_source_count | `5147` |
| window_row_count | `None` |
| window_size | `None` |

Source kind counts:

```json
{
  "artifact_file": 60246,
  "doc": 73,
  "script": 4140,
  "summary": 5147
}
```

Source ledgers:

```json
[
  "runs/pocketpal_seq2seq_runs.jsonl",
  "runs/ledgers/pocketpal_seq2seq_runs.jsonl"
]
```

Siblings listed by the Hugging Face API:

```json
[
  ".gitattributes",
  "README.md",
  "manifest.json",
  "train.parquet"
]
```


## Hugging Face Parquet Recovery

Downloaded timeline parquet:

`runs/local/artifacts/remote_recovery/hf_100m_swe_research_timeline/files/train.parquet`

Inspection artifact:

`runs/local/artifacts/remote_recovery/hf_100m_swe_research_timeline/parquet_inspection.json`

Parquet facts:

- bytes: `58775830`
- sha256: `4effdb90e8887d8aac75141c0d0612eaeb4487ea0737560ea1828f0932fa2af1`
- rows: `5615`
- row groups: `1`
- stage_min: `1`
- stage_max: `6158`

Last observed stage rows include Stage6149-6158, centered on repo-skill/prompt-to-skill ranking and native constrained-rank planning. This confirms the Hugging Face archive is an early/mid research timeline source, not a source for Stage8400-8587 decoder/structured-maintainer recovery.

## Hugging Face Recovery Use

The Hugging Face dataset is a strong archive for the early and mid research timeline, but its `stage_max` is `6158`. It cannot recover the Stage8400-8587 decoder/structured-maintainer branch.

Use it for:

- Stage1-6158 chronology reconstruction
- early KBPP / semantic-compression frontier notes
- source bundle and summary bundle references
- older script/doc/artifact inventory
- validating durable research-spine continuity before Stage7933/8031/8141

Do not use it for:

- Stage8500+ active bounded decoder CE authority
- Stage8580 trainer safety surface
- late repo-state graph, bounded decoder, or cleanup incident details

## Integration Plan

1. Keep all remote files in `runs/local/artifacts/remote_recovery/` until reviewed.
2. Rebuild active code from remote files only by explicit patch, never wholesale overwrite.
3. Compare GitHub legacy trainer/dataset builders against recovered safety contracts before reuse.
4. Use Hugging Face timeline as an older research-memory source, not as active stage registry truth.
5. Keep Codex session recovery as the source of truth for Stage8530-8587.
6. Preserve the closed authority rule: remote recovery opens no training/runtime/decode authority.

## Current Rebuild Priority After External Recovery

- Finish control-plane safety and registry rebuild.
- Patch trainer command surface only after safe cleanup and loss-mask enforcement are tested.
- Restore dataset judge / curriculum compiler / manifest builders from reviewed sources and session-derived contracts.
- Re-run non-executing audits before any tiny bounded decoder CE probe.
