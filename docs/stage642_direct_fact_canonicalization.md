# Stage642 Direct-Fact Canonicalization

Artifact: `runs/local/artifacts/stage642_direct_fact_canonicalization_summary.json`

## Summary

Stage642 tests whether the Stage641 direct-fact selector gain can be canonicalized instead of accumulated.

Stage641 added `{domain}|{field}|{entity}` on top of older direct-fact markers. Stage642 keeps the winning marker and removes older direct-fact scaffolding variants.

## Results

| variant | exact | answer | direct_fact exact | direct_fact answer | avg train retrieval tokens | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| remove `entity:field` | `0.9747863247863248` | `0.985897435897436` | `1.0` | `1.0` | `154.46555516452577` | `59` |
| remove `domain:entity:field` | `0.9747863247863248` | `0.985897435897436` | `1.0` | `1.0` | `152.886811543199` | `59` |
| keep new marker only | `0.9726495726495726` | `0.9846153846153847` | `0.9842271293375394` | `0.9905362776025236` | `150.12401020587717` | `64` |

## Decision

Accepted `remove domain:entity:field` as the canonical Stage642 direct-fact surface.

It preserves the full Stage641 gain while reducing average train retrieval tokens per pair from Stage641's `157.22835650184763` to `152.886811543199`. Removing both older markers is too aggressive and loses direct-fact perfection.

## Updated Rule

The current best direct-fact representation is:

```text
<AK_OP_DIRECT_FACT> domain|field|entity entity:field ...
```

The old `domain:entity:field` scaffold is redundant once `domain|field|entity` is present. The shorter `entity:field` marker still matters for the current checkpoint.

Next route: canonicalize the rest of the selector map with the same discipline: remove only scaffolding proven redundant by promotion-grade eval, not by token count alone.
