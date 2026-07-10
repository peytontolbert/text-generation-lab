# Stage9995 Source Overlap Eval Hacking Audit

Passed: `True`
Source-overlap eval rows: `39`
Semantic-overlap eval rows: `77`

Audited the filtered frontier for eval hacking risk by checking train-versus-eval overlap on source roots and semantic keys.

Next: Use the source-heldout subset, not the raw filtered frontier, for any honest 100M-versus-Gemma comparison and rebuild future eval manifests to avoid train-overlapping roots.
