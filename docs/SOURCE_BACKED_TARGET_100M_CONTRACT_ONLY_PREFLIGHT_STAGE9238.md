# Stage9238 Source-Backed Target 100M Contract-Only Preflight

Passed: `true`

The Stage9237 source-backed bounded decoder tiny manifest passed the target-100M trainer contract in contract-only mode. No model execution occurred.

## Contract

- Manifest: `runs/local/artifacts/stage9237_source_backed_bounded_decoder_tiny_package/source_backed_bounded_decoder_tiny_manifest.jsonl`
- Manifest SHA256: `4b148d62f8b1165cb0d69a712f34a54a0e11626e8e53dc17373d26f5f7e092c3`
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

With explicit authorization, run the tiny target-100M source-backed bounded decoder probe under trellis with generation audit enabled.
