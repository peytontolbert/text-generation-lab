# Stage640 Direct-Fact Hard Negatives

Artifact: `runs/local/artifacts/stage640_direct_fact_hardneg_summary.json`

## Summary

Stage640 tests the Stage639 diagnosis with structured direct-fact hard negatives.

Dataset:

- selected direct-fact train answer misses ranked `2-3`: `496`
- rank histogram: rank `2` = `13`, rank `3` = `483`
- negatives per replay row: `3`
- negative types:
  - same `domain+field`, different entity
  - same `domain+entity`, different field
  - same field, different domain

Training:

- initialized from Stage636
- `40` steps
- learning rate `2e-7`
- hard-negative weight `0.05`
- hard-negative margin weight `0.02`

## Results

| run | exact | answer | direct_fact exact | direct_fact answer | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stage636 frontier | `0.9692307692307692` | `0.9803418803418803` | `0.9589905362776026` | `0.9589905362776026` | `72` |
| Stage640 direct hard-neg | `0.9688034188034188` | `0.9803418803418803` | `0.9589905362776026` | `0.9589905362776026` | `73` |

## Decision

Rejected as a frontier.

The hard negatives did not move direct-fact held-out accuracy. They also reproduced the same global exact loss seen in Stage638 by lowering `set_intersection_member` exact from `0.979381443298969` to `0.9742268041237113`.

## Updated Rule

Direct-fact is not fixed by replay or hard-negative loss on the current card format. The next route should change the representation:

- split direct facts into an entity selector plus value card;
- or add a compact direct-value selector that isolates `domain`, `entity`, and `field` roles without relying on the broad current fact card;
- evaluate the direct-fact slice before global continuation, because unrelated exact-card slices are easy to damage.
