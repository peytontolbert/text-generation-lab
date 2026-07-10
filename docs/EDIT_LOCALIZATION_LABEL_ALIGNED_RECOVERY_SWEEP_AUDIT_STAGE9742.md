# Stage9742 Edit Localization Label-Aligned Recovery Sweep Audit

Passed: `True`
Baseline eval/strict exact: `0.14285714285714285` / `0.14285714285714285`
Best sweep run: `steps128_lr5e5`
Best sweep eval/strict exact: `0.14285714285714285` / `0.14285714285714285`
Improved runs: `[]`

This stage records a second negative result: after label alignment, simply running longer still does not improve multilingual edit-localization.

Next: Stop adding identical step budget to the repaired edit-localization package. The next change must alter curriculum, labels, or comparison packaging rather than just train longer.
