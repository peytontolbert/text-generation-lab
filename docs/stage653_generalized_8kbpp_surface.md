# Stage653 Generalized 8 KBPP Surface

Artifact: `runs/local/artifacts/stage653_generalized_8kbpp_surface.json`

## Result

- Eval units: `48411`
- Train units: `55029`
- Verified hidden eval bits: `298195.65456578933`
- Perfect ceiling at 16,280 params: `18.316686398390008` KBPP
- 8 KBPP target bits: `130240.0`
- Target margin: `167955.65456578933` bits (`2.289585799798751`x)

## Family Mix

| family | train | eval | eval bits |
|---|---:|---:|---:|
| `abstractions` | 144 | 1152 | 6912.0 |
| `atomic_facts` | 34560 | 20736 | 124416.0 |
| `counterfactual_and_negative_knowledge` | 4604 | 9220 | 55320.0 |
| `multi_hop_compositions` | 3082 | 10742 | 64452.0 |
| `procedures` | 2215 | 857 | 9054.0 |
| `relations_and_sets` | 10424 | 5704 | 38041.654565776014 |

## Collision Conditioning

- Eval collision groups: `362`
- Groups with collisions: `362`
- Rows in collision groups: `48411`
- Mean candidate count: `133.73204419889504`
- Max candidate count: `652`

## Decision

Stage653 establishes the next entropy rung. It is accepted as a surface only, not as a trained-model win. The next required step is a 16k initialized no-filter training probe on this manifest, scored by `scripts/score_general_kbpp_eval.py` and the retrieval evaluator. Hard-filter-only recovery remains excluded from neural KBPP.
