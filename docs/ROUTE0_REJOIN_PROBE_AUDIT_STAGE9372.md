# Stage9372 Route0 Rejoin Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `224` / `250`
Target-prefix rows: `224` / `250`
Boundary next-token rows: `238` / `250`
Contentful rows: `250` / `250`
Short/junk rows: `0`
Repetition rows: `0`
Leak rows: `0`

Route_0 dependency duplicate rows rejoined cleanly: `93 / 93` exact. The remaining residual is narrow:

- Residual rows: `26`
- Residual routes: `{'route_2': 12, 'route_file_path': 14}`
- Residual tasks: `{'clean_prefix_to_phrase_completion': 1, 'file_path_localized_edit_repair': 4, 'file_path_patch_inside_intrusion_repair': 6, 'localized_edit_file_path_bridge': 2, 'numeric_preserves_omission_repair': 6, 'observed_or_synthetic_phrase_error_to_clean_target': 4, 'prefix_ladder_to_remaining_suffix': 1, 'repair_file_path_associated_with': 2}`

Decoder CE, runtime, Gemma, harness, source/body emission, scoring, promotion, and controller merge remain closed.
