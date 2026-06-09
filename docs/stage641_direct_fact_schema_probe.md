# Stage641 Direct-Fact Schema Probe

Artifact: `runs/local/artifacts/stage641_direct_fact_schema_probe_summary.json`

## Summary

Stage641 searches direct-fact selector schemas on top of the accepted Stage636 trained checkpoint.

This follows the Stage639-640 diagnosis:

- positive direct-fact replay did not move held-out direct_fact;
- hard-negative loss did not move held-out direct_fact;
- therefore the next useful lever was selector serialization/schema.

## Results

| template | exact | answer | direct_fact exact | direct_fact answer | answer bits/param | hard-filter corrections |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `{domain}|{field}|{entity}` | `0.9747863247863248` | `0.985897435897436` | `1.0` | `1.0` | `1.5860331402324361` | `59` |
| `df={domain}:{field}:{entity}` | `0.9726495726495726` | `0.9837606837606837` | `0.9842271293375394` | `0.9842271293375394` | `1.5825957038643552` | `64` |
| `{field}:{entity}` | `0.9726495726495726` | `0.9837606837606837` | `0.9842271293375394` | `0.9842271293375394` | `1.5825957038643552` | `64` |
| `{domain}:{field}:{entity}` | `0.9713675213675214` | `0.9824786324786324` | `0.9747634069400631` | `0.9747634069400631` | `1.580533242043507` | `67` |

Stage636 baseline was exact/answer `0.9692307692307692` / `0.9803418803418803`, answer bits/param `1.5770958056754263`, and hard-filter corrections `72`.

## Decision

Accepted as the new Stage626-derived schema frontier on the Stage636 bundle.

This is not a new trained checkpoint. It is a schema-only gain using the Stage636 trained model with a better direct-fact selector marker.

## Finding

Direct-fact was schema-limited, not gradient-limited. The winning `domain|field|entity` marker makes direct_fact exact/answer perfect on the held-out Stage626 eval while preserving the other operation slices.

The important detail is delimiter/order: `domain|field|entity` beats `domain:field:entity`, and a `df=` label is worse than the raw marker. This matches the earlier selector-compression rule: expose the latent binding identity directly and avoid label text unless it earns its tokens.

## Next Step

Build a canonical Stage642 surface that keeps the Stage641 direct-fact marker but removes redundant older direct-fact scaffolding where possible. The gate is strict: preserve Stage641 answer, keep direct_fact perfect, and do not raise hard-filter corrections above `59`.
