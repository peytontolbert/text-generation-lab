# Stage9675 Neutral Slot Prior Denoise Probe Audit

Passed: `False`
Safety passed: `True`
Exact rows: `6` / `26`
Target-prefix rows: `6` / `26`
Contentful rows: `25` / `26`
Repetition rows: `1`
By slot: `{'approved_library_entry': {'rows': 4, 'exact': 4, 'target_prefix': 4, 'repetition': 0, 'exact_rate': 1.0, 'target_prefix_rate': 1.0}, 'callable_endpoint': {'rows': 4, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'concrete_value': {'rows': 1, 'exact': 0, 'target_prefix': 0, 'repetition': 1, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'constant_value': {'rows': 2, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'dependency_handle': {'rows': 2, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'file_path': {'rows': 3, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'local_name': {'rows': 2, 'exact': 2, 'target_prefix': 2, 'repetition': 0, 'exact_rate': 1.0, 'target_prefix_rate': 1.0}, 'method_invocation_target': {'rows': 5, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'project_path': {'rows': 2, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}, 'small_constant': {'rows': 1, 'exact': 0, 'target_prefix': 0, 'repetition': 0, 'exact_rate': 0.0, 'target_prefix_rate': 0.0}}`

Neutral slot features helped compared with literal suffix-choice labels, but this is still not a generation pass.

Next: Build Stage9676 slot-specific micro-support manifest for failing neutral slots; do not widen denoise generation until exact/contentful/repetition gates pass.
