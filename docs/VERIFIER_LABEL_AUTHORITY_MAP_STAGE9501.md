# Stage9501 Verifier Label Authority Map

Passed: `True`
Rows: `66`

## Decision

Verifier-derived labels may be trained as telemetry/representation heads, but no verifier head may authorize acceptance, decoder promotion, scoring, runtime, or harness execution. Effective authority stays with deterministic verifier observations and transition records.

## Field Authority

| Field | Effective authority | Learned role | May authorize acceptance |
| --- | --- | --- | --- |
| `episode_boundary_match` | `deterministic_overlay` | `telemetry_only` | `False` |
| `episode_target_prefix_match` | `deterministic_overlay` | `telemetry_and_representation_probe` | `False` |
| `episode_failure_type` | `deterministic_normalizer` | `telemetry_only_until_isolated_probe_passes` | `False` |
| `episode_repair_outcome` | `transition_record` | `telemetry_only_until_isolated_probe_passes` | `False` |
| `episode_step_value` | `deterministic_reward` | `value_estimate_only` | `False` |

## Probe Evidence

- Stage9486 target-prefix isolated probe passed: `True`
- Stage9492 all-verifier observe probe passed: `False`
- Stage9500 boundary deterministic overlay passed: `True`

The next verifier rejoin must use deterministic effective verifier fields for authority and treat learned verifier outputs as calibration/diagnostic telemetry.
