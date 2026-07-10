# Stage9963 Blended Weak-Language Target100M Contract Preflight

Passed: `True`
Total rows: `452`
Aggregate loss counts: `{'edit_localization_ce': 120, 'patch_operator_ce': 144, 'symbol_binding_ce': 80, 'verifier_repair_ce': 108}`

Ran target-100M contract-only trainer preflights for the stage9962 weak-language successor mix; this preserves the same no-execution boundary while validating the next run contract after adding the real python, c_cpp, and web recovery roots.

Next: Use these preflighted manifests as the next capped blended target-100M structured run contract; the edit-localization leg now carries the web recovery rows plus the stage9961 weak-language recovery roots inside the same contract-only-validated trainer path.
