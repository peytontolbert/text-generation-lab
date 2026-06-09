# Recursive KBPP Selector Hill-Climb

Script: `scripts/recursive_kbpp_selector_hillclimb.py`

Smoke artifact: `runs/local/artifacts/recursive_kbpp_selector_hillclimb_smoke.json`

## Purpose

This script automates the Stage610-615 pattern:

1. Build selector-schema variants from a source dataset.
2. Optionally evaluate each variant with the current retrieval checkpoint.
3. Rank candidates by answer bits/param, optionally with a retrieval-token penalty.

## Example

Build candidates without evaluation:

```bash
/home/peyton/miniconda3/envs/ai/bin/python scripts/recursive_kbpp_selector_hillclimb.py \
  --templates '{entity}|{field}' 'sp={entity}|{field}' \
  --run-eval 0
```

Run evaluated search:

```bash
/home/peyton/miniconda3/envs/ai/bin/python scripts/recursive_kbpp_selector_hillclimb.py \
  --templates '{entity}|{field}' 'sp={entity}|{field}' '{field}|{entity}' \
  --run-eval 1 \
  --token-penalty 0.0001
```

## Finding

Use this to recursively search compact latent selector anchors. The current best manual result is Stage615: raw `entity|field` without role-token scaffolding.
