# Stage9599 Suffix-Choice Residual Denoise Reconnect Design

Passed: `True`
Sidecar rows: `96`
Denoise source rows: `41`

Design: run a two-phase closed probe. Phase 1 trains the `suffix_choice_ce` controller under encoder RoPE and frozen decoder/export buckets. Phase 2 uses that effective choice to condition residual-denoise rendering with decoder CE/runtime/export still closed.

Next: Implement a contract-only two-phase suffix-choice plus residual-denoise reconnect wrapper; do not execute nonzero denoise until that wrapper audit passes.
