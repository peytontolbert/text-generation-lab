# Stage9385 Prefix-Primed Bounded Decoder Failure Denoise Manifest

Passed: `True`
Rows: `23`
Splits: `{'eval': 9, 'strict_eval': 7, 'train': 7}`
Routes: `{'EOS_CALIBRATION': 11, 'USE_FOR_DENOISE_REPAIR': 12}`

This keeps decoder CE closed and exposes only a short active generation prefix, not the full target.
