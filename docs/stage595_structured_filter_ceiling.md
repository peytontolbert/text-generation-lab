# Stage595 Structured Filter Ceiling

Artifact: `runs/local/artifacts/stage595_structured_filter_ceiling.json`

## Result

Strict full-corpus operation-gated retrieval with `--structured-key-rerank 1 --structured-key-hard-filter 1` makes both 16k models exact/answer perfect.

| run | no-filter exact/answer | hard-filter exact/answer | corrections | damage | hard-filter bits/param |
|---|---:|---:|---:|---:|---:|
| Stage525 | `0.9746168582375478` / `0.9841954022988506` | `1.0` / `1.0` | `53` | `0` | `1.4143899091423784` |
| Stage594 | `0.9755747126436781` / `0.9846743295019157` | `1.0` / `1.0` | `51` | `0` | `1.4143899091423784` |

Both hard-filter runs have exactly one exact-key candidate for every query, zero missing correct candidates, and zero multiple-candidate queries.

## Decision

`deterministic_access_ceiling_confirmed_not_pure_neural_frontier`

## Finding

Exact structured-key hard filtering raises both 16k Stage525 and Stage594 to perfect strict full-corpus exact/answer retrieval with zero damage. Because every query has exactly one exact-key candidate and the correct document is always inside that candidate set, this is a verifier/access-layer ceiling rather than pure neural KBPP. The result says the current schema is too key-separable for measuring further intelligence density; the next dataset must introduce controlled key collisions or hidden compositions where exact keys narrow the candidate set but do not solve it.

## Next Schema Requirement

The next KBPP benchmark should create key-collision-conditioned examples: exact operation/domain keys should narrow retrieval but leave more than one candidate, forcing the tiny model to resolve value, relation, or composition information inside the filtered set.
