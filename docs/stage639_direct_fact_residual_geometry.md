# Stage639 Direct-Fact Residual Geometry

Artifact: `runs/local/artifacts/stage639_direct_fact_residual_geometry.json`

## Summary

Stage639 analyzes Stage636 direct-fact residuals before spending more training on them.

The key problem: direct-fact has a large train near-miss pool, but prior positive replay did not improve held-out direct-fact accuracy.

## Findings

Stage636 train split:

- direct-fact rows: `4486`
- exact misses: `744`
- answer misses: `708`
- answer misses ranked `2-3`: `496`

Stage636 eval split:

- direct-fact rows: `317`
- exact misses: `13`
- answer misses: `13`

Held-out answer-miss relation pattern:

| relation | count |
| --- | ---: |
| different domain, different entity, different field, different answer | `6` |
| same domain, different entity, same field, different answer | `3` |
| different domain, different entity, same field, different answer | `2` |
| same domain, different entity, different field, different answer | `2` |

So this is not a simple exposure problem. Every held-out direct-fact answer miss changes entity and answer; most also change domain or field. Positive replay alone is unlikely to create the missing local contrast.

## Next Step

Build a direct-fact hard-negative surface:

- same `domain+field`, different entity;
- same `domain+entity`, wrong field;
- same field across nearby domains.

The objective should push the correct direct card away from these structured neighbors. Do not replay direct-fact positives alone again unless this contrastive surface also fails.
