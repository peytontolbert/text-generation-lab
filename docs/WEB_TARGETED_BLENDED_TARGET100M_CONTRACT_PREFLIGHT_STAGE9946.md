# Stage9946 Web Targeted Blended Target100M Contract Preflight

Passed: `True`
Total rows: `404`
Aggregate loss counts: `{'edit_localization_ce': 72, 'patch_operator_ce': 144, 'symbol_binding_ce': 80, 'verifier_repair_ce': 108}`

Ran target-100M contract-only trainer preflights for the stage9945 blended structured-state successor mix; this preserves the same no-execution boundary while validating the next run contract after the web-targeted refresh was blended in.

Next: Use these preflighted manifests as the next capped blended target-100M structured run contract; the edit-localization leg now carries the targeted web refresh rows inside the same contract-only-validated trainer path.
