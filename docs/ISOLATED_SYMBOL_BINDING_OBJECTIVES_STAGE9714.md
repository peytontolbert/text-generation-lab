# Stage9714 Isolated Symbol-Binding Objectives

Stage9714 splits the two unsolved Stage9713 transitions out of the mixed five-way symbol-binding objective.

## Manifests

- `symbol_binding_test_coverage_binary.jsonl`: test query rows only, TEST_BINDS_VISIBLE_SYMBOL vs TEST_NEEDS_RETRIEVAL.
- `symbol_binding_retrieve_gate_ternary.jsonl`: all rows collapsed to BIND_AVAILABLE, RETRIEVE_MORE, or ABSTAIN_UNBOUND.

## Result

- Passed: `True`
- Test binary rows: `32`
- Retrieve gate rows: `92`

## Next

Run contract-only preflight for one isolated Stage9714 objective at a time, starting with test_coverage_binary; do not rejoin five-way symbol binding until isolated exactness passes.
