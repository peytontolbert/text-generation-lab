# Stage9600 Two-Phase Suffix/Denoise Contract Preflight

Passed: `True`
Phase 1 contract passed: `True`
Phase 2 contract passed: `True`

This stage validates existing trainer contracts for the two pieces separately. It does not execute training and does not yet implement the in-memory two-phase wrapper.

Next: Patch the trainer with an audited two-phase in-memory wrapper that can run suffix_choice training before denoise repair without checkpoint export.
