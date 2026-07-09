# Stage9667 Sidecar-Gated Residual Denoise Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Exact rows: `5` / `26`
Target-prefix rows: `5` / `26`
Contentful rows: `26` / `26`
Short/junk rows: `0`
Repetition rows: `0`
Internal leak rows: `0`
By repair bucket: `{'REPAIR_PREFIX_AND_BOUNDARY': {'rows': 10, 'exact': 0, 'target_prefix': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'REPAIR_PREFIX_ONLY': {'rows': 16, 'exact': 5, 'target_prefix': 5, 'exact_rate': 0.3125, 'target_prefix_rate': 0.3125}}`

The probe is safe and contentful but not exact. The next patch should add approved clean prefix spans as model input and use a generation-prefix-field, without exposing the full target.

Next: Build Stage9668 prefix-primed sidecar residual denoise manifest using approved clean prefix spans; keep decoder/runtime/Gemma/harness closed.
