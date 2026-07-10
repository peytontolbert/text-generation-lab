# Stage10028 Deduped Source-Heldout Same-Manifest Comparison Audit

Passed: `True`
Decision: Materialized the deduped source-heldout same-manifest 100M-versus-Gemma comparison on unique heldout eval rows so the honest multilingual frontier can be stated without duplicate-row collapse.

Next: Use this deduped source-heldout comparison as the clean baseline, then replenish Python and c_cpp with fresh independent heldout roots instead of replaying the current tied rows.
