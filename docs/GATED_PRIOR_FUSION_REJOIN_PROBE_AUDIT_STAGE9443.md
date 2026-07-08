# Stage9443 Gated Prior Fusion Rejoin Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`

Generated rows: `50`
Exact rows: `21` / `50`
Target-prefix rows: `21` / `50`
Boundary next-token rows: `37` / `50`
Contentful rows: `47` / `50`
Short/junk rows: `0`
Repetition rows: `2`
Unterminated rows: `3`
Leak rows: `0`
Heldout exact rows: `1` / `2`

Decoder CE remains closed. The next step is residual diagnosis, not widening.

## Episode/Step Curriculum Note

This probe remains a single-step denoise transition. The larger maintainer curriculum should keep episodes as ordered sequences of observe/orient/action/verify/repair steps, with each step yielding a typed state-action-observation transition row for supervised or verifier-rewarded training.
