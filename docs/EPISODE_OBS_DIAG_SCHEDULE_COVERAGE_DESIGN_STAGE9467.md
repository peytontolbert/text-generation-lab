# Stage9467 Episode Observation Diagnosis Schedule Coverage Design

Passed: `True`
Rows: `50`
Train rows: `48`
Max steps: `96`
Train exposure cycles: `4`

Stage9466 proved representation learnability under balanced repeated support; Stage9467 restores the full 50-row manifest but requires enough deterministic training steps to cover all 48 train rows four times.

Only structured episode diagnosis losses are allowed. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
