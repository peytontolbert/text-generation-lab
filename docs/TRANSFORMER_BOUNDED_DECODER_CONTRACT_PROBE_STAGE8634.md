# Stage8634 Transformer Bounded Decoder Contract Probe

This stage runs the safe trainer in `--contract-only` mode against the reconstructed 64-row bounded decoder CE loss-mask package while selecting `--implementation transformer`. It does not instantiate the model or train.

## Result

- contract passed: `True`
- rows: `64`
- split counts: train `32`, eval `16`, strict `16`
- unsafe loss rows: `0`
- authority rows: `0`
- over-cap rows: `0`
- implementation selected: `transformer`
- model execution attempted: `False`

## Important Caveat

The manifest rows are reconstructed replacement rows from Stage8592, not original Stage8568 row bodies. This is enough to validate the control plane and loss-mask plumbing, but not enough to claim decoder capability.

## Still Closed

Model execution, decoder CE training, runtime, source/body emission, Gemma, harness/scoring, controller merge, and promotion remain closed.
