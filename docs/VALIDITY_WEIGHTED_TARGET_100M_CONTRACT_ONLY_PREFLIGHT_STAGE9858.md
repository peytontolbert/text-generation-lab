# Stage9858 Validity-Weighted Target-100M Contract-Only Preflight

Passed: `True`
Total rows: `456`
Aggregate loss counts: `{'decoder_ce': 64, 'edit_localization_ce': 60, 'patch_operator_ce': 144, 'symbol_binding_ce': 80, 'verifier_repair_ce': 108}`
Failures: `[]`

This stage splits the Stage9857 validity-weighted package into trainer-compatible surface manifests and validates each command contract under target_100m without running model execution or training.

No runtime, source/body emission, Gemma, harness, scoring, model execution, checkpoint export, training execution, or promotion is authorized.

Next: Promote the passed Stage9858 manifests into a capped structured execution review for the new validity-weighted package, then authorize a single target-100M structured probe series against the cleaned v2.7 mix.
