# Stage9471 Episode Observation Diagnosis Checkpoint-Selection Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Paired checkpoint records: `13`
Both-exact checkpoints: `[]`

Interval telemetry found no step where eval success and strict residual were both exact. The result oscillates by checkpoint, consistent with deterministic batch order and residual-heavy class exposure; next patch should use balanced ordered train rows or a balanced sampler.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
