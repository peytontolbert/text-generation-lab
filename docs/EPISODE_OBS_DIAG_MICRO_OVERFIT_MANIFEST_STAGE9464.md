# Stage9464 Episode Observation Diagnosis Micro-Overfit Manifest

Passed: `True`
Rows: `18`
Splits: `{'eval': 1, 'strict_eval': 1, 'train': 16}`
Cells: `{'prefix=False|outcome=residual_suffix_repair_step': 9, 'prefix=True|outcome=successful_suffix_repair_step': 9}`

Test whether target-100M structured heads can learn the success/residual verifier-observation rule under balanced repeated support before returning to the full 50-row manifest.

Only episode diagnosis losses are enabled. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
