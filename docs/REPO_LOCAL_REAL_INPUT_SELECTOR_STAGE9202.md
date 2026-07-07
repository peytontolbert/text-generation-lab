# Stage9202 Repo-Local Real Input Selector

Passed: `True`

This stage validates repo-local candidate bundles, previews materialization under the recovered contract,
and selects one reusable real-input bundle without invoking the trainer.

Still closed:
- trainer execution
- model forward
- runtime

Next: Feed the selected bundle into the next contract-only real probe family handoff, or add another repo-local candidate bundle and let the selector choose between them.
