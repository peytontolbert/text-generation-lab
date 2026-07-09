# Stage9608 Prefix-Primed Suffix Continuation Failure Audit

Passed: `True`
Prefix start rate: `1.0`
Boundary next-token match rate: `0.9166666666666666`
Target prefix match rate: `0.0`
Degenerate repetition rate: `0.8333333333333334`
Loss first/last: `88.58428192138672` / `6.569724082946777`

Finding: the reconnect is no longer failing at the controller or prefix boundary. It fails after the first suffix token, usually by repeating local fragments such as `localized by the localized`, `relevant rep`, or `inv inv`.

Next: Build Stage9609 suffix-continuation ladder/support manifest from Stage9605, then run contract-only preflight before another tiny probe.
