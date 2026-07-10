# Stage9895 Current Margin Locality Signal Label Remap Probe Audit

Passed: `True`
Eval exact: `0.4375`
Strict exact: `0.5`
Prediction counts: `{'R': 12, 'T': 8, 'Z': 12}`
Removed single-label collapse: `True`

The Stage9894 remap control does not improve headline exact over the locality-lift baseline, but it removes the single-label K collapse. That is strong evidence that class-token geometry, not just packet semantics, still limits the current 100M edit-localization head.

Next: Promote the locality-signal lift as an eval-valid evidence improvement, then test a neutral output vocabulary or head/objective redesign on the main current-frontier packet.

