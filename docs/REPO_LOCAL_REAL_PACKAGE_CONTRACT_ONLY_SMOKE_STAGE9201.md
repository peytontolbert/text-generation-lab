# Stage9201 Repo-Local Real Package Contract-Only Smoke

Passed: `True`

This stage uses existing repo-local compiler outputs as real inputs, materializes route cards / loss masks / trainer rows,
and runs one structured-policy trainer invocation in contract-only mode.

Still closed:
- model execution
- runtime
- decoder CE execution
- denoise execution

Next: Promote this repo-local real-package handoff into a reusable audited input selector, then repeat the same contract-only path for the next eligible real probe family before any explicit execution authorization.
