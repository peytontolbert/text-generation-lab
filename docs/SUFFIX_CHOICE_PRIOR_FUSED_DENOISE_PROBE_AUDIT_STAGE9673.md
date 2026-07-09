# Stage9673 Suffix Choice Prior Fused Denoise Probe Audit

Passed: `False`
Safety passed: `True`
Exact rows: `0` / `26`
Target-prefix rows: `0` / `26`
Generation-prefix-start rows: `26` / `26`
Contentful rows: `18` / `26`
Repetition rows: `8`
Internal leak rows: `0`

The suffix-choice sidecar is learnable, but injecting literal suffix-choice labels into denoise generation made output worse than Stage9669 and reintroduced repetition.

Next: Reject literal suffix-choice-prior generation branch; build Stage9674 neutral slot-feature prior manifest or keep suffix_choice as controller-only telemetry before generation.
