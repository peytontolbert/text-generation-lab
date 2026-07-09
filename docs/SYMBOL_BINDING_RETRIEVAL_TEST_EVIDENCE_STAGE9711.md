# Stage9711 Symbol-Binding Retrieval/Test Evidence Repair

Stage9711 strengthens the two Stage9710 residual failures without reopening decoder work: retrieve-more gaps and test-coverage binding.

## Repair

- Adds opaque retrieval-gap relation edges for retrieve-more rows.
- Adds opaque test coverage evidence nodes/edges for test binding rows.
- Adds import/call resolution relation edges for comparison without exposing target label names in model input.
- Keeps row count and split caps unchanged from Stage9708.

## Result

- Passed: `True`
- Rows: `92`
- Query-kind baseline: `0.445652`
- Strongest single-feature baseline: `0.75`

## Next

Run Stage9712 contract-only preflight for the Stage9711 retrieval/test evidence manifest; only then consider a short target-100M retry.
