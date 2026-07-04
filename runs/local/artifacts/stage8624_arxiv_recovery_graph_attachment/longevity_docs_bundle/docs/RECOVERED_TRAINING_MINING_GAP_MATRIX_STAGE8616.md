# Stage8616 Training And Mining Gap Matrix

Stage8616 separates three different recovery states:

- executable recovered components,
- conceptually recovered but not executable components,
- components that are candidates only and still not authorized for training.

This prevents a dangerous mistake: treating recovered research language as recovered mining/training code.

## Current Verdict

Broad mining is not fully recovered.

Training is not ready.

The software-maintainer map is substantially recovered, but several objective-specific miners and audits still need to be rebuilt before `/arxiv/datasets` and `/arxiv/repositories` can be mined broadly.

## Executable Or Partially Executable Now

### `repo_capability_catalog`

Status: executable recovered.

Present scripts:

- `scripts/index_arxiv_software_corpus.py`
- `scripts/build_stage8601_arxiv_repo_capability_and_graph_seed.py`
- `scripts/audit_stage8602_arxiv_repo_capability_graph_seed.py`

Safe next use:

- read-only catalog and seed audits.

### `repo_state_graph_v1`

Status: seed executable recovered.

Present scripts:

- `scripts/build_stage8601_arxiv_repo_capability_and_graph_seed.py`
- `scripts/audit_stage8602_arxiv_repo_capability_graph_seed.py`

Current gap:

- full graph-family miners are not restored.
- recovered graph families from Stage8615 need proper miners:
  - `GRAPH_DATA_RUNTIME_IO`
  - `GRAPH_INTERFACE_BOUNDARY`
  - `GRAPH_MODEL_TRAIN_EVAL`
  - `GRAPH_AGENT_TOOLING`
  - `GRAPH_GENERIC_LIBRARY`
  - `GRAPH_TEST_VERIFIER`

Safe next use:

- extend graph-family coverage only behind opaque-ID, endpoint, split, and shortcut audits.

### `symbol_binding`

Status: partial executable recovered.

Present scripts:

- `scripts/build_stage8603_arxiv_symbol_binding_candidates.py`
- `scripts/build_stage8610_symbol_binding_counterfactual_patch.py`
- `scripts/audit_stage8611_symbol_binding_counterfactual_patch.py`

Current gap:

- `BIND_TEST_TO_SYMBOL` is missing.
- `test` query coverage is missing.
- Stage8611 still blocked training.

Safe next use:

- limited mining of true `BIND_TEST_TO_SYMBOL` rows.
- no training until the action/query coverage and shortcut audit pass.

### `bounded_decoder_ce`

Status: candidate package recovered, not authorized.

Present scripts:

- `scripts/build_stage8564_v27_bounded_decoder_ce_candidate_package_design.py`
- `scripts/audit_stage8565_v27_bounded_decoder_ce_candidate_package_design_audit.py`
- `scripts/build_stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design.py`
- `scripts/audit_stage8569_v27_bounded_decoder_ce_loss_mask_reopen_design_audit.py`
- `scripts/audit_stage8583_v27_bounded_decoder_ce_patched_final_pre_execution_audit.py`

Current gap:

- upstream structured objective rows are incomplete.
- decoder execution authority remains closed.

Safe next use:

- non-executing audits only.

## Conceptually Recovered But Not Executable

These are recovered in docs/config/session ledgers, but their miners and objective-specific audits are not restored.

### `intent_to_build_strategy`

Recovered concept:

```text
user intent + import/repo constraints
-> USE_WHITELIST_IMPORT | BUILD_ON_TOP | BUILD_FROM_SCRATCH
```

Needed scripts:

- neutral masked objective manifest builder.
- shortcut audit for first-action, plan-keyword, allowed-import-count, available-repo-count, and direct-target-field leaks.

Do not train until:

- strongest single/combo baselines are below ceiling.
- build modes and languages are balanced.
- direct target fields are absent from model input.

### `edit_localization`

Recovered concept:

```text
intent + repo graph + binding evidence
-> target file / symbol / config / test / retrieve / abstain
```

Needed scripts:

- objective manifest builder.
- endpoint and opaque-ID audit.
- graph-shape/degree-profile shortcut audit.
- counterfactual rows with same graph shape but different target.

### `patch_operator`

Recovered concept:

```text
localized edit need
-> MODIFY_EXISTING_SYMBOL | INSERT_FUNCTION | REPLACE_EXPR | WRAP_CALL | ADD_IMPORT | ADD_TEST_CASE | UPDATE_CONFIG_FIELD | CREATE_FILE | BUILD_ADAPTER | ROLLBACK_PATCH | RETRIEVE_MORE | ABSTAIN_UNSAFE
```

Needed scripts:

- objective manifest builder.
- operator/target shortcut audit.
- counterfactual rows where same target requires different operator and same operator targets different objects.

### `verifier_repair`

Recovered concept:

```text
failure log + patch context
-> diagnose / localize / repair / rerun / rollback / retrieve
```

Needed scripts:

- manifest builder from baseline-valid verifier/failure logs.
- no-runtime-authority audit.
- candidate verifier and behavior-value labels from Stage8615:
  - `BV_ACCEPT_READY`
  - `BV_NEEDS_VERIFIER`
  - `BV_REJECT_OR_ABSTAIN`
  - `BV_FALSE_ACCEPT_RISK`
  - `CANDIDATE_PASS_VERIFIED`
  - `CANDIDATE_NEEDS_TEST`
  - `CANDIDATE_FAIL_BEHAVIOR`
  - `CANDIDATE_FAIL_INTERFACE`

Runtime verification remains closed; this objective can only use existing logs/artifacts until a later authority gate opens runtime.

### `bounded_decoder_arguments`

Recovered concept:

```text
operator + graph state
-> small bounded argument text
```

Needed scripts:

- argument manifest builder.
- budget/target audit.
- no copied target text in model input.
- semantic surface audit.

### `output_repair_denoise`

Recovered concept:

```text
bad output + verifier failure + target state
-> repaired bounded output
```

Needed scripts:

- denoise repair manifest builder.
- short/junk, repetition, leak, and wrong-surface audits.

Current blocker:

- no current measured decoder failures from the rebuilt workspace.
- generation/training remains closed.

## Training Must Stay Closed

Before any model training resumes, every objective must have:

- source inventory card,
- dataset judge route,
- authority card,
- loss-mask card,
- counterfactual obligation card,
- shortcut baseline card,
- duplicate semantic key card,
- split-overlap card,
- budget/evidence card,
- telemetry contract card.

The recovered 100M path is still:

```text
repo capability catalog
-> repo_state_graph_v1
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder arguments
-> bounded decoder CE
-> output repair denoise
```

## Immediate Safe Work

1. Mine true `BIND_TEST_TO_SYMBOL` rows.
2. Rebuild `intent_to_build_strategy` neutral masked miner.
3. Rebuild edit-localization miner.
4. Rebuild patch-operator miner.
5. Rebuild verifier-repair miner from existing failure/verifier logs only.
6. Rebuild bounded-decoder-argument miner.
7. Only after those pass, revisit bounded decoder CE.

## Hard Stop

Do not start broad mining or training from `/arxiv` yet.

The current safe scope is limited recovery and targeted objective reconstruction, not dataset-scale ingestion.
