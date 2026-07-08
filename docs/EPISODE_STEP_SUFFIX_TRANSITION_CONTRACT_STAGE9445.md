# Stage9445 Episode-Step Suffix Transition Contract

Passed: `True`

This stage folds the RL episode/step framing into the 100M maintainer curriculum.

- Episode: a complete maintenance attempt.
- Step: one `state_t, action_t, verifier/reward, state_t_plus_1` transition.
- Current suffix-choice denoise rows: step-level repair transitions, not a standalone decoder capability.

The next compiler patch should emit episode ids, step indices, phase labels, verifier failure fields, route-local suffix targets, and strict per-step loss masks.

Decoder CE, runtime, Gemma, harness, hidden scoring, body/source emission, and promotion remain closed.
