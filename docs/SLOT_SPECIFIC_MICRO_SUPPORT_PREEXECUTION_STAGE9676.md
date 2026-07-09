# Stage9676 Slot-Specific Micro-Support Preexecution

Passed: `True`
Rows: `43`
Original rows: `26`
Support rows: `17`
Split counts: `{'eval': 3, 'strict_eval': 3, 'train': 37}`
Support slot counts: `{'callable_endpoint': 2, 'concrete_value': 1, 'constant_value': 2, 'dependency_handle': 2, 'file_path': 2, 'method_invocation_target': 4, 'project_path': 2, 'small_constant': 2}`

This package keeps the Stage9674 eval/strict rows held out and adds train-only support for the Stage9675 failing slot families. The small-constant support rows are synthetic diagnostic analogs, not copied heldout targets.

Only `denoise_ce` is active. Decoder CE, runtime, Gemma, harness, scoring, checkpoint export, and promotion remain closed.

Next: If Stage9676 passes, execute Stage9677 slot-specific micro-support denoise probe and audit exact/contentful/repetition by slot.
