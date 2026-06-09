# Materialized Environment Snapshot

This repo contains a first-pass source snapshot from `/data/agent_kernel_lite` under `legacy_src/`.

## Snapshot Summary

- lab: Seq2seq text
- source root: `/data/agent_kernel_lite`
- copied files: 415
- copied size: 187M
- inventory manifest: `manifests/current_environment.json`
- materialization script: `scripts/materialize_selected_files.py`

## Included By Default

- training and diagnostic scripts
- docs and tests where detected
- text configs, prompt files, metadata, ledgers, JSON/JSONL/CSV/TOML/YAML files
- relevant model-stack source references

## Excluded By Default

- checkpoints and model binaries: `.pt`, `.safetensors`, `.bin`, `.onnx`
- generated image/audio media: `.png`, `.jpg`, `.jpeg`, `.wav`, `.mp3`
- cache and local runtime artifacts
- files larger than the materializer size limit unless explicitly copied later

Use this snapshot as the extraction base, then progressively move active files from `legacy_src/` into first-class lab packages and scripts.
