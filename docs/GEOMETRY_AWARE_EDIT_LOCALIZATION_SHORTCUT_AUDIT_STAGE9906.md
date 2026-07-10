# Stage9906 Geometry-Aware Edit Localization Shortcut Audit

Passed: `True`
Validated buckets: `8`
Prompt exposes valid-label line in all buckets: `True`
All rows use fixed label order: `False`

Audited the current geometry-aware edit-localization comparison surface and found that the prompt still exposes the full label vocabulary on every bucket. Candidate positions are no longer fully fixed, but the current same-surface margin is still not hardened against label-proxy shortcuts.

Next: Do not upgrade Stage9901 into a robust multilingual win claim. Rebuild the current geometry-aware comparison surface so prompts do not reveal the valid label list and candidate IDs are row-randomized or hidden behind constrained opaque outputs, then rerun the same-surface Gemma comparison.
