# Stage9388 Bounded Decoder Short-Suffix Bridge Manifest

Passed: `True`
Rows: `23`
Splits: `{'eval': 9, 'strict_eval': 7, 'train': 7}`
Routes: `{'EOS_CALIBRATION': 11, 'USE_FOR_DENOISE_REPAIR': 12}`
Suffix word counts: `{'7': 23}`

This stage preserves the active generation prefix but shortens the clean target to a small verified suffix span. The original full target remains hidden by hash only.
