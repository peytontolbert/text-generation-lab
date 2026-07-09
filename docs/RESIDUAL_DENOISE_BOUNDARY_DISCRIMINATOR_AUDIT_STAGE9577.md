# Stage9577 Residual Denoise Boundary Discriminator Audit

Passed: `True`
Sample balanced: `True`
Boundary recall: `0.0`
Prefix recall: `1.0`
Evidence gate passed: `True`
Learned collapse confirmed: `True`

The next issue is not sample bias. Boundary evidence is present, but the denoise decoder still emits the prefix-only class for all sampled rows.

Next: build a boundary-evidence amplified manifest before any widening.
