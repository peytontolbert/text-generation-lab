# Stage9801 Opaque Choice Option Token Decoder Manifest

Passed: `True`
Rows: `60`
Splits: `{'eval': 20, 'strict_eval': 20, 'train': 20}`
Languages: `{'c_cpp': 15, 'python': 15, 'rust': 15, 'web_js_ts_html': 15}`
Decoder texts: `{'option A': 12, 'option B': 12, 'option C': 12, 'option D': 12, 'option E': 12}`

This stage changes only the decoder target format, from bare A-E labels to `option X`, while preserving the corrected Stage9790 visible evidence surface.

Next: Run a bounded decoder CE preexecution and one real probe on the Stage9801 manifest, then compare it against the Stage9799 single-letter decoder path and the Stage9794 structured baseline.

