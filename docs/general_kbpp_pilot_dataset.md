# General KBPP Pilot Dataset

Generated pilot: `runs/local/tmp/general_kbpp_pilot_v1/general_kbpp_pilot_manifest.json`

This is the first concrete dataset built from the general KBPP schema. It is not a final benchmark yet; it is a pilot for testing the unit schema, split accounting, candidate-space entropy, and verifier interface.

## Contents

- Total knowledge units: `1357`
- Train-visible units: `1212`
- Hidden eval units: `145`
- Available hidden eval verified bits: `399.4944302478051`
- Eval query rows: `145`

## Unit Coverage

- `atomic_fact`: `1024` total, `72` eval, `165.7653742946046` eval bits
- `relation`: `128` total, `16` eval, `64.0` eval bits
- `composition`: `64` total, `16` eval, `32.0` eval bits
- `counterfactual_false_claim`: `64` total, `22` eval, `50.08519976342583` eval bits
- `math_identity`: `32` total, `7` eval, `63.0` eval bits
- `exception`: `16` total, `8` eval, `16.0` eval bits
- `procedure`: `5` total, `2` eval, `4.643856189774724` eval bits
- `causal_rule`: `4` total, `1` eval, `2.0` eval bits
- `code_api_semantics`: `4` total, `1` eval, `2.0` eval bits
- `schema`: `16` total, `0` eval, `0.0` eval bits

## Read

The pilot now exercises more than memorized facts: hidden eval includes relations, two-hop compositions, false-claim corrections, math identities, procedures, causal rules, and code/API semantics. It still needs a larger and better-balanced hidden split before it can serve as a serious 7B useful-KBPP baseline.

## Scoring

Scorer: `scripts/score_general_kbpp_eval.py`

Oracle score artifact: `runs/local/artifacts/general_kbpp_pilot_oracle_score_100m.json`

The scorer now takes predictions over `general_kbpp_eval_queries.jsonl` and reports verified bits, KBPP, generalization KBPP, composition KBPP, and an EID proxy. The oracle checksum recovers all `399.4944302478051` hidden eval bits.

Next step: train/evaluate the 1k-to-100M ladder against this scorer, then expand the pilot until 7B-class models no longer saturate the hidden split.
