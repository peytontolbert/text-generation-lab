# Stage9472 Episode Observation Diagnosis Balanced-Order Manifest

Passed: `True`
Rows: `58`
Splits: `{'eval': 1, 'strict_eval': 1, 'train': 56}`
Cells: `{'prefix=False|outcome=residual_suffix_repair_step': 29, 'prefix=True|outcome=successful_suffix_repair_step': 29}`

Rows alternate success/residual so deterministic two-row batches see both cells every step.

Only episode diagnosis losses are enabled. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
