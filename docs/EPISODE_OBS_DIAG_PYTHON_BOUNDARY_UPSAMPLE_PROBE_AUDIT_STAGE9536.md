# Stage9536 Episode Observation Diagnosis Python Boundary Upsample Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Regressed vs Stage9528: `True`
Final eval exact: `0.16666666666666666`
Final strict exact: `0.16666666666666666`
Wrong rows: `10`
High-confidence wrong rows: `6`

Safe severe regression. Train-only Python boundary upsampling overcorrected the failure-type head and should not be promoted.
