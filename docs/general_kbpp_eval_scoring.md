# General KBPP Eval Scoring

Scorer: `scripts/score_general_kbpp_eval.py`

Pilot oracle score: `runs/local/artifacts/general_kbpp_pilot_oracle_score_100m.json`

Oracle predictions: `runs/local/tmp/general_kbpp_pilot_v1/oracle_predictions.jsonl`

## Contract

The scorer consumes hidden eval rows from `general_kbpp_eval_queries.jsonl` and model predictions in JSONL form:

```json
{"unit_id":"gkbpp_...","answer":"..."}
```

Each hidden unit contributes `log2(candidate_space)` verified bits only when the normalized prediction exactly matches the expected answer. Missing predictions, extra predictions, and duplicate prediction IDs are reported explicitly.

## Metrics

- `verified_bits`: entropy-weighted hidden knowledge recovered by the model.
- `kbpp`: `verified_bits / param_count`.
- `generalization_kbpp`: verified bits per parameter on held-out splits.
- `composition_kbpp`: verified bits per parameter on two-hop composition units.
- `eid_proxy`: depth-weighted verified bits divided by `param_count * inference_compute_proxy`.

Depth weights are intentionally conservative for now:

- Atomic facts: `1.0`
- Relations/schemas: `1.05`
- Exceptions: `1.15`
- Procedures, causal rules, math identities, code/API semantics, false-claim corrections: `1.2` to `1.25`
- Two-hop compositions: `1.5`

## Oracle Check

The oracle predictions recover the full hidden pilot:

- Eval units: `145`
- Verified bits: `399.4944302478051`
- Weighted verified bits: `445.6724342479337`
- Accuracy: `1.0`
- 100M-normalized KBPP ceiling on this pilot: `3.994944302478051e-06`
- 100M-normalized generalization KBPP ceiling: `3.0140923048437936e-06`
- 100M-normalized composition KBPP ceiling: `3.2e-07`
- 100M-normalized EID proxy ceiling: `4.456724342479337e-06`

## Finding

The current pilot is a measurement harness, not a decisive benchmark. Its total hidden entropy is intentionally small, so the absolute 100M KBPP ceiling is tiny. The important new result is that the research now has a strict hidden-unit scoring contract spanning facts, relations, compositions, false-claim correction, math, procedures, causal rules, and code/API semantics.

The next useful step is to train/evaluate small checkpoints against this scorer, then expand the dataset until larger models no longer saturate it.
