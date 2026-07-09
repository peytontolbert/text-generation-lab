# Stage9500 Boundary Verifier Overlay Contract

Passed: `True`
Rows: `26`
Effective boundary exact: `1.0`
Effective false boundary accepts: `0`
Stage9496 learned wrong rows: `4`
Stage9496 high-confidence wrong rows: `4`
Stage9499 learned wrong rows: `4`
Stage9499 high-confidence wrong rows: `0`

## Contract

`episode_boundary_match` is a deterministic verifier primitive for effective acceptance:

`effective_boundary_match = observation_t.boundary_next_token_match`

The learned boundary head remains telemetry-only. It must not authorize boundary acceptance or decoder promotion.

## Rationale

Stage9496 learned a true-majority shortcut with high-confidence false-boundary accepts. Stage9499 removed that collapse through counterbalancing, but the target-100M head fell to chance with low margins. This makes the label useful as a verifier fact, not as model authority.
