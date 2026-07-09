# Stage9489 Full Episode Observe-Prefix Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Final eval joint: `0.5`
Final strict joint: `0.6`
Wrong rows: `9`
High-confidence wrong rows: `0`

Safe quality failure. Moving target-prefix to observe-phase helped during interval evaluation, but the jointly exact restore gate never opened because verifier-derived failure_type/outcome/value are still being trained as pre-action targets. The next patch should make episode verifier fields phase-aware instead of treating all five heads as one policy surface.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
