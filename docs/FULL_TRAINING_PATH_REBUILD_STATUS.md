# Full Training Path Rebuild Status

This is the current recovery boundary for getting back to training after the workspace-loss incident.

## Rebuilt

- safe cleanup/path guards
- stage registry
- authority gate
- loss-mask validation
- shortcut audit utility
- deterministic junk/routing ranker
- trainer command-surface scaffold
- bounded decoder probe wrapper design/audit
- bounded decoder CE loss-mask reopen builder/audit

## Still Missing For Real Training

- original Stage8564 bounded decoder CE candidate row bodies
- original Stage8568 loss-mask row bodies
- upstream bounded decoder argument row bodies
- actual trainer execution implementation behind the safe command surface
- final pre-execution audit on real rows
- explicit tiny execution authorization

## Immediate Rebuild Target

Bring back the data path needed before training:

```text
bounded_decoder_argument_rows
-> bounded_decoder_ce_candidate_package
-> decoder_ce_loss_mask_rows
-> wrapper/final pre-execution audit
```

Counts recovered from sessions:

- candidate package rows: 96
- candidate splits: 32 / 32 / 32
- candidate languages: 24 each
- candidate surfaces: 24 each
- selected loss-mask rows: 64
- selected splits: 32 / 16 / 16
- selected languages: 16 each
- selected surfaces: 16 each
- surfaces: MAINTAINER_EXPLANATION_ARGS, REPAIR_PLAN_ARGS, PATCH_HUNK_ARGS, TEST_PLAN_ARGS

Important rule: if row bodies are regenerated, mark them reconstructed. Do not claim they are original recovered artifacts.
