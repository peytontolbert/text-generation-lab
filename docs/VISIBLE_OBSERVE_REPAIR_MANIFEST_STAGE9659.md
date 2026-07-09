# Stage9659 Visible Observe/Repair Manifest

Passed: `True`
Rows: `66`
Splits: `{'train': 54, 'eval': 6, 'strict_eval': 6}`
Loss counts: `{'episode_boundary_match_ce': 66, 'episode_target_prefix_match_ce': 66}`
Relation baselines: `{'model_boundary_token_relation->boundary_match': 1.0, 'model_target_prefix_relation->target_prefix_match': 1.0}`
Non-relation baselines: `{'language_family->boundary_match': 0.803030303030303, 'language_family->target_prefix_match': 0.6363636363636364, 'active_generation_prefix_span->boundary_match': 0.8636363636363636, 'active_generation_prefix_span->target_prefix_match': 0.7575757575757576}`

This stage moves the successful Stage9658 model-input comparator pattern back into broader observe/repair episode rows. The focused scope is boundary-next-token and target-prefix verifier heads only.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.

Next: If Stage9659 passes, run Stage9660 visible observe/repair target-100M boundary-prefix probe.
