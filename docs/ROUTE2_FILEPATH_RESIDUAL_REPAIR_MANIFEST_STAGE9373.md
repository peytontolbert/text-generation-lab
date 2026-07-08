# Stage9373 Route2/Filepath Residual Repair Manifest

Passed: `True`
Rows: `26`
Splits: `{'eval': 4, 'strict_eval': 11, 'train': 11}`
Routes: `{'route_2': 12, 'route_file_path': 14}`
Tasks: `{'file_path_verified_to_localized_repair': 14, 'numeric_preserves_omission_repair': 12}`
Surfaces: `{'file_path_argument': 14, 'numeric_argument': 12}`

This manifest isolates the Stage9372 safe-but-not-quality residual: route_2 numeric `preserves` omission and route_file_path `verified edit` to `localized edit` substitution. Decoder CE and external authority remain closed.
