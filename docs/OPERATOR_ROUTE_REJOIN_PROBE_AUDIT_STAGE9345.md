# Stage9345 Operator Route Rejoin Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `43` / `74`
Target-prefix match rows: `43` / `74`
Boundary next-token match rows: `64` / `74`
Contentful rows: `74` / `74`
Degenerate repetition rows: `0`
Short/junk rows: `0`
Internal leak rows: `0`
Error counts: `{'file_path_localized_edit_bridge': 2, 'keeps_token_omission': 5, 'keepside_subword_bridge': 7, 'patch_operator_subword_bridge': 19}`

Safety held: decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export stayed closed.

The quality failure is now a subword/bridge problem rather than a repetition collapse. The dominant errors are `keepside`, missing `keeps`, `pator` for `patch operator`, and a file-path row drifting from `localized edit` to the operator fragment.

The full mixture also needs feature-schema normalization. Some base rows do not carry the same route/surface/affordance feature set as the Stage9340 repair rows, so another full-mixture rejoin should wait until those features are aligned.
