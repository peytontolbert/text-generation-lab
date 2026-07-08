# Stage9400 Suffix Second-Span Residual Diagnosis

Passed: `True`
Heldout residual rows: `11`
Residuals with boundary token fixed: `7`
Residuals by split: `{'eval': 7, 'strict_eval': 4}`
Residual families: `{'current repair invariant. Do not introduce an': 2, 'expected assertion behavior. Keep the value small': 2, 'localized edit target. Keep the path reference': 2, 'patch inside the whitelist. Use the symbol': 1, 'patch operator should update. Use the repo': 2, 'the repaired state. Keep the answer focused': 2}`

Diagnosis: Stage9399 fixed much of the first-token problem, but exact heldout recovery is now blocked by continuation after the boundary token.

Next: build train-only analogous support rows for the failing 7-word post-prefix spans. Keep decoder CE, runtime, Gemma, harness, source/body emission, and promotion closed.
