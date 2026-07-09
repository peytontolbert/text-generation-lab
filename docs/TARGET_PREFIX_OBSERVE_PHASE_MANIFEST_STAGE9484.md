# Stage9484 Target-Prefix Observe-Phase Manifest

Passed: `True`
Rows: `66`
Splits: `{'eval': 6, 'strict_eval': 6, 'train': 54}`
Label leak rows: `0`
Generated evidence visible rows: `66`
Reference evidence visible rows: `66`

This manifest moves target-prefix from hidden-observation pre-action guessing to observe-phase verifier training. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
