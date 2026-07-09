# Stage9713 Symbol-Binding Retrieval/Test Evidence Execution

- Execution boundary passed: `True`
- Quality passed: `False`
- Eval exact: `0.45454545454545453`
- Strict exact: `0.4090909090909091`
- Decoder delta norm: `0.0`

## Diagnosis

- ABSTAIN_UNBOUND, BIND_IMPORT_TO_MODULE, and BIND_CALL_TO_SYMBOL are now mostly learned.
- BIND_TEST_TO_SYMBOL remains 0 exact and collapses to ABSTAIN_UNBOUND.
- RETRIEVE_MORE remains 0 exact and splits between ABSTAIN_UNBOUND and BIND_CALL_TO_SYMBOL.

## Next

Build Stage9714 isolated binary/ternary objectives for test coverage binding and retrieve-more gating; mixed five-way symbol binding still hides those two transitions.
