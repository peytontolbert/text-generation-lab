# Stage9677 Slot-Specific Micro-Support Denoise Probe Audit

Passed: `False`
Safety passed: `True`
Exact rows: `4` / `43`
Target-prefix rows: `4` / `43`
Contentful rows: `31` / `43`
Repetition rows: `12`
By slot: `{'approved_library_entry': {'rows': 4, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 4, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}, 'callable_endpoint': {'rows': 6, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 6, 'contentful_rate': 1.0, 'repetition': 1, 'repetition_rate': 0.16666666666666666}, 'concrete_value': {'rows': 2, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 2, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}, 'constant_value': {'rows': 4, 'exact': 4, 'exact_rate': 1.0, 'target_prefix': 4, 'target_prefix_rate': 1.0, 'contentful': 4, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}, 'dependency_handle': {'rows': 4, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 4, 'contentful_rate': 1.0, 'repetition': 4, 'repetition_rate': 1.0}, 'file_path': {'rows': 5, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 5, 'contentful_rate': 1.0, 'repetition': 5, 'repetition_rate': 1.0}, 'local_name': {'rows': 2, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 2, 'contentful_rate': 1.0, 'repetition': 2, 'repetition_rate': 1.0}, 'method_invocation_target': {'rows': 9, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 9, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}, 'project_path': {'rows': 4, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 4, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}, 'small_constant': {'rows': 3, 'exact': 0, 'exact_rate': 0.0, 'target_prefix': 0, 'target_prefix_rate': 0.0, 'contentful': 3, 'contentful_rate': 1.0, 'repetition': 0, 'repetition_rate': 0.0}}`

The train-only support package did not solve the residual suffix repair. It overfit `constant_value` and reintroduced repeated localized/verified/reference spans across other slot families.

This branch is rejected. Continue from Stage9674/9675 with a repetition guard or a structured slot-span ladder rather than adding more duplicate denoise rows.

Next: Do not build further on Stage9676 duplicates; branch back to Stage9674/9675 and add a repetition guard or structured slot-span ladder before any new denoise generation.
