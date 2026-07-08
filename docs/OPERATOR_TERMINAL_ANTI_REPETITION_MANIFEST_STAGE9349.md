# Stage9349 Operator Terminal Anti-Repetition Manifest

Passed: `True`
Rows: `17`
Splits: `{'eval': 7, 'strict_eval': 2, 'train': 8}`
Routes: `{'route_1': 17}`

This manifest isolates the Stage9348 route_1 failure: `patch operatch ... operator`. It keeps the solved dependency and file-path bridge rows out of the repair set and trains only denoise CE.

Decoder CE, runtime, harness, Gemma, scoring, source/body emission, checkpoint export, controller merge, and promotion remain closed.
