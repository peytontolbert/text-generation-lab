# Arxiv Corpus Recovery Index

Stage8600 re-anchors the rebuild to the local corpora:

- `/arxiv/datasets`
- `/arxiv/repositories`

This is a read-only inventory. It does not authorize model execution, decoder CE training, runtime execution, source/body emission, Gemma, harness scoring, controller merge, or promotion.

## Dataset Inventory

Indexed dataset files: `2530`

Suffix counts:

- `.parquet`: `2376`
- `.jsonl`: `87`
- `.md`: `39`
- `.json`: `23`
- `.zip`: `2`
- `.csv`: `1`
- `.gz`: `1`
- `.tar`: `1`

Software-maintenance-name hits: `450`

Internal-marker name hits: `0`

Initial use:

- inventory only until schema audit
- candidate SWE datasets for structured rows
- long-output holdout sources
- denoise/repair candidates
- regression and abstain/retrieve negatives

No dataset file should create gradients until it receives:

- route
- authority card
- loss mask
- duplicate check
- shortcut audit
- budget/evidence status

## Repository Inventory

Repository directories seen: `607`

Repository directories indexed: `500`

Truncated repository scans: `16`

Language/file counts from indexed repos:

- Python: `151171`
- Web JS/TS/HTML/CSS: `150695`
- C/C++ family: `142527`
- Docs: `102540`
- Config: `97919`
- Java/JVM: `88190`
- Go: `82634`
- Rust: `32446`
- Shell: `11441`

Build-system signal is strong:

- `package.json`: `1243`
- `CMakeLists.txt`: `1216`
- `requirements.txt`: `908`
- `Makefile`: `790`
- `pyproject.toml`: `691`
- `Cargo.toml`: `589`
- `setup.py`: `246`
- `pom.xml`: `223`
- `go.mod`: `217`
- `go.sum`: `184`

Recommended curriculum-use counts from the first 500 repos:

- `repo_capability_catalog`: `496`
- `maintainer_qa`: `496`
- `bounded_decoder_arguments`: `465`
- `patch_operator`: `465`
- `intent_to_build_strategy`: `436`
- `repo_state_graph_v1`: `436`
- `symbol_binding`: `381`
- `edit_localization`: `381`
- `verifier_repair`: `381`

This is enough to restart the software-maintainer path, provided rows are compiled through typed objectives instead of raw codegen.

## What This Restores

The local repositories can support:

- repo capability catalogs
- import/build-system detection
- dependency-policy examples
- symbol/import/call/test graph extraction
- edit localization candidates
- patch operator examples
- verifier/failure repair rows
- bounded decoder argument rows

The local datasets can support:

- prior SWE timelines and traces after schema audit
- structured state rows
- retrieve/abstain negatives
- long-output holdouts
- denoise repair rows
- promotion/regression examples

## Required Next Compiler Work

Build objective-specific manifests from `/arxiv` in this order:

1. `repo_capability_catalog`
2. `repo_state_graph_v1`
3. `intent_to_build_strategy`
4. `symbol_binding`
5. `edit_localization`
6. `patch_operator`
7. `verifier_repair`
8. `bounded_decoder_arguments`
9. `bounded_decoder_ce`
10. `output_repair_denoise`

Each compiler output must include:

- `rows.jsonl`
- `cell_card.json`
- `loss_card.json`
- `shortcut_audit.json`
- `authority_card.json`
- `duplicate_card.json`
- `budget_evidence_card.json`
- `stage_summary.json`

## Safety Rule

Do not train directly on `/arxiv` files.

Correct path:

```text
/arxiv source
-> read-only inventory
-> dataset judge/ranker
-> typed curriculum compiler
-> objective manifest
-> loss-mask card
-> non-executing audit
-> tiny gated probe only if authorized
```

Current authority remains closed.

