# Stage9360 Non-Operator Rejoin Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `99` / `154`
Target-prefix rows: `99` / `154`
Boundary next-token rows: `140` / `154`
Contentful rows: `154` / `154`
Short/junk rows: `0`
Degenerate repetition rows: `0`
Internal leak rows: `0`
Error counts: `{'file_path_localized_edit_omission': 6, 'file_path_patch_inside_intrusion': 6, 'operator_subword_pator': 25, 'operator_unverified_terminal': 24, 'operator_verified_omission': 48}`

Safety held, but full-mixture exactness is not clean enough to reopen bounded decoder CE.
The remaining residuals are route_1 `verified patch operator` omissions/subword drift and route_file_path `localized edit` intrusion from `patch inside`.
