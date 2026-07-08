# Stage9361 Mixture Interference Residual Repair Manifest

Passed: `True`
Rows: `55`
Splits: `{'eval': 17, 'strict_eval': 11, 'train': 27}`
Tasks: `{'file_path_patch_inside_intrusion_repair': 6, 'operator_pator_subword_terminal_repair': 25, 'operator_verified_omission_repair': 24}`
Routes: `{'route_1': 49, 'route_file_path': 6}`
Surfaces: `{'edit_action_argument': 49, 'file_path_argument': 6}`

This manifest isolates the Stage9360 rejoin residuals: route_1 `verified patch operator` omissions/subword drift and route_file_path `localized edit` drift.
Decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export remain closed.
