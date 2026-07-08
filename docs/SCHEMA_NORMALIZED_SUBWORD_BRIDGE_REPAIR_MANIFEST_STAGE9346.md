# Stage9346 Schema-Normalized Subword Bridge Repair Manifest

Passed: `True`
Rows: `31`
Splits: `{'eval': 10, 'strict_eval': 4, 'train': 17}`
Tasks: `{'dependency_handle_keeps_the_bridge': 12, 'localized_edit_file_path_bridge': 2, 'patch_operator_subword_bridge': 17}`
Routes: `{'route_0': 12, 'route_1': 17, 'route_file_path': 2}`
Surfaces: `{'dependency_handle': 12, 'edit_action_argument': 17, 'file_path_argument': 2}`

This manifest converts Stage9345 exact-match failures into denoise-only repair rows. It normalizes the model-visible route/surface/affordance schema and trains only the corrupted-output-to-clean-target repair transition.

Decoder CE, runtime, harness, Gemma, scoring, source/body emission, checkpoint export, controller merge, and promotion remain closed.
