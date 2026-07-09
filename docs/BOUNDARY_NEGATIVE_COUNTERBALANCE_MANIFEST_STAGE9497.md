# Stage9497 Boundary Negative Counterbalance Manifest

Passed: `True`
Rows: `26`
Splits: `{'eval': 4, 'strict_eval': 4, 'train': 18}`
Label counts: `{'eval::False': 2, 'eval::True': 2, 'strict_eval::False': 2, 'strict_eval::True': 2, 'train::False': 9, 'train::True': 9}`

This manifest balances true/false boundary labels per split and adds deterministic comparison features to `model_input`.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
