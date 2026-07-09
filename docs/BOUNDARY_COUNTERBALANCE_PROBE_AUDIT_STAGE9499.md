# Stage9499 Boundary Counterbalance Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Final eval exact: `0.5`
Final strict exact: `0.5`
Wrong rows: `4`
High-confidence wrong rows: `0`

Safe quality failure. Counterbalancing removed the high-confidence true-majority collapse from Stage9496, but the boundary head now sits near chance with low margins. The next repair should add stronger deterministic boundary-comparison features or route this label to a non-learned verifier overlay.
