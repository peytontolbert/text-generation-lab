# Stage643 Entity Schema Probe

Artifact: `runs/local/artifacts/stage643_entity_schema_probe_summary.json`

## Summary

Stage643 applies the schema-search rule to `entity_context` after the Stage642 direct-fact canonical frontier.

Entity replay had already saturated, so this tests selector serialization rather than another training run.

## Results

| template | exact | answer | entity exact | entity answer | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{domain}|{field}|{entity}` | `0.9811965811965812` | `0.9918803418803419` | `0.9756944444444444` | `0.9756944444444444` | `1.595657962063062` | `44` |
| `{domain}|{entity}|{field}` | `0.9811965811965812` | `0.9918803418803419` | `0.9756944444444444` | `0.9756944444444444` | `1.595657962063062` | `44` |
| `{entity}|{field}` | `0.9803418803418803` | `0.9910256410256411` | `0.96875` | `0.96875` | `1.5942829875158297` | `46` |
| `{field}|{entity}` | `0.9786324786324786` | `0.9893162393162394` | `0.9548611111111112` | `0.9548611111111112` | `1.5915330384213652` | `50` |

Stage642 baseline was exact/answer `0.9747863247863248` / `0.985897435897436`, answer bits/param `1.5860331402324361`, and hard-filter corrections `59`.

## Decision

Accepted `{domain}|{field}|{entity}` as the new Stage626-derived schema frontier on the Stage636 trained checkpoint.

`{domain}|{entity}|{field}` ties, but `{domain}|{field}|{entity}` matches the Stage642 direct-fact canonical rule, so it is the cleaner shared selector.

## Finding

Entity-context was schema-limited after all. Earlier entity replay saturated because the representation was still missing a clean raw selector. As with direct_fact, a compact pipe-delimited identity beats more training.

Next route: canonicalize entity_context around `{domain}|{field}|{entity}` and then refresh residual details. The remaining answer misses should be mostly rule/member families.
