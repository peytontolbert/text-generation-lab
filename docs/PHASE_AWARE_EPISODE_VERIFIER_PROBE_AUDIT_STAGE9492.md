# Stage9492 Phase-Aware Episode Verifier Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Final eval joint: `0.5333333333333333`
Final strict joint: `0.5`
Wrong rows: `29`
High-confidence wrong rows: `0`

Safe quality failure. Combined observe-phase verifier heads collapsed toward majority/default classes on the tiny 66-row set. Target-prefix alone is learnable, but all verifier labels together need either deterministic verifier-feature overlays or per-head staged curricula before rejoining.
