# Stage9444 Gated Prior Rejoin Residual Diagnosis

Passed: `True`
Residual rows: `29` / `50`
Suffix/token miss rows: `29`
Quality residual rows: `3`

The remaining failure is not broad decoder collapse. It is mostly step-local continuation choice under prefix-primed denoise rows, plus a small repetition/unterminated pocket.

## Episode/Step Implication

A full maintainer episode should be broken into steps. Each step should train one transition:

`state_t + action_t + verifier_observation_t -> repaired_state_or_next_action_t`

For decoder repair, the current suffix-choice task should be represented as a step-level repair transition with route-local evidence, target continuation, verifier failure, and next-state label. This avoids treating multiple repair routes as one flat denoise surface.

Decoder CE remains closed.
