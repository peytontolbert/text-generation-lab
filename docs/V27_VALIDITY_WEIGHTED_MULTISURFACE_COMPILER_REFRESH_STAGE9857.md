# Stage9857 V2.7 Validity-Weighted Multisurface Compiler Refresh

Passed: `True`
Rows: `456`
Skill counts: `{'bounded_argument_rendering': 64, 'edit_localization': 60, 'patch_operator_selection': 144, 'symbol_binding': 80, 'verifier_failure_repair_or_abstain': 108}`
Loss counts: `{'decoder_ce': 64, 'edit_localization_ce': 60, 'patch_operator_ce': 144, 'symbol_binding_ce': 80, 'verifier_repair_ce': 108}`

This stage replaces the old v2.7 multisurface training mix with a validity-weighted successor: stronger multilingual edit localization goes in, explicit abstention guardrails replace invalid hard surfaces, and single-surface loss masks remain enforced.

No runtime, source/body emission, Gemma, harness, scoring, model execution, checkpoint export, or promotion is authorized by this stage.

Next: Use this validity-weighted compiled package as the next v2.7 training mix: stronger multilingual edit-localization winner surface in, abstention-only patch/verifier guardrails in, and stale forced-action rows out.

