# Stage8941 Positional Embedding Ignore Policy

Passed: `True`

This stage records the default policy for the source-only learned encoder positional embedding artifact: ignore it unless a future architecture audit proves a compatible recovered target key/module exists. It does not copy tensors, mutate architecture, load/write checkpoints, run a model, train, or execute runtime.

Policy rows: `1`
