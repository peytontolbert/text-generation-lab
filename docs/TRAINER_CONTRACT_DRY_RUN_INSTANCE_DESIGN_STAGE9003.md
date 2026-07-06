# Stage9003 Trainer Contract Dry-Run Instance Design

Passed: `True`

This stage designs the exact future trainer contract-only dry-run instance needed by Stage9002. It does not invoke the trainer, load model weights, load dataset row bodies, run forward/backward, write checkpoints, train, mine data, or authorize decoder/denoise CE.

Dry-run instance ready to execute: `False`
Required inputs: `5`
Required outputs: `10`

The instance remains blocked until locked manifest, loss-mask, schema, and contamination/leakage proof artifacts exist and a separate execution authorization stage passes.
