# Stage9352 Full Mixture With Schema And Terminal Repairs Manifest

Passed: `True`
Rows: `122`
Splits: `{'eval': 36, 'strict_eval': 21, 'train': 65}`
Sources: `{'base_schema_normalized': 74, 'operator_terminal_repair': 17, 'schema_bridge_repair': 31}`
Routes: `{'route_0': 30, 'route_1': 68, 'route_2': 12, 'route_file_path': 12}`
Surfaces: `{'dependency_handle': 30, 'edit_action_argument': 68, 'file_path_argument': 12, 'numeric_argument': 12}`

The original full mixture is schema-normalized before rejoining the Stage9346 and Stage9349 repair rows. Decoder CE, runtime, harness, Gemma, scoring, promotion, and checkpoint export remain closed.
