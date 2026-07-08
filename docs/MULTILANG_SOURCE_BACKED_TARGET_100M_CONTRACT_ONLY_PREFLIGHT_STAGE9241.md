# Stage9241 Multi-Language Source-Backed Target 100M Contract-Only Preflight

Passed: `true`

The Stage9240 balanced source-backed bounded decoder tiny manifest passed target-100M trainer contract checks in contract-only mode. No model execution occurred.

## Contract

- Manifest: `runs/local/artifacts/stage9240_source_backed_multilang_bounded_decoder_tiny_package/source_backed_multilang_bounded_decoder_tiny_manifest.jsonl`
- Manifest SHA256: `69575019a44ed44c159f0b66ed161eb4ae788bb7d719b939e8c438dc44958e1b`
- Rows: `64`
- Splits: `{'eval': 16, 'other': 0, 'strict_eval': 16, 'train': 32}`
- Loss counts: `{'action_sequence_ce': 0, 'allowed_import_policy_ce': 0, 'blocked_import_policy_ce': 0, 'build_mode_ce': 0, 'decoder_ce': 64, 'denoise_ce': 0, 'edit_localization_ce': 0, 'file_plan_ce': 0, 'patch_operator_ce': 0, 'repair_surface_ce': 0, 'repo_dependency_policy_ce': 0, 'runtime_reward': 0, 'surface_role_ce': 0, 'symbol_binding_ce': 0, 'verifier_repair_ce': 0}`
- Authority rows: `0`
- Unsafe loss rows: `0`
- Over-cap rows: `0`
- Empty target rows: `0`
- Model execution attempted: `False`

## Boundary

Runtime, Gemma, harness/scoring, source/body emission, checkpoint export, controller merge, and promotion remain closed.

## Next

Create a fresh inactive execution review for this balanced manifest. Execute only after explicit user authorization.
