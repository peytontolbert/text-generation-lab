# Stage9746 Multilingual Structured Surface Comparison Refresh

Passed: `True`
Best surface: `edit_localization_target_only`
Ranking: `['edit_localization_target_only', 'verifier_repair', 'patch_operator']`
Surface metrics: `{'verifier_repair': {'eval_exact': 0.1111111111111111, 'strict_exact': 0.1111111111111111, 'baseline_eval_exact': 0.25, 'baseline_strict_exact': 0.25}, 'edit_localization_target_only': {'eval_exact': 0.2, 'strict_exact': 0.2, 'baseline_eval_exact': 0.14285714285714285, 'baseline_strict_exact': 0.14285714285714285}, 'patch_operator': {'eval_exact': 0.08333333333333333, 'strict_exact': 0.08333333333333333, 'baseline_eval_exact': 0.0, 'baseline_strict_exact': 0.0}}`

This stage refreshes the current executed 100M structured-surface ranking after the stronger target-only edit-localization intervention. It is still not a Gemma comparison.

Next: Treat the refreshed best surface as the strongest current standalone multilingual 100M comparison candidate; Gemma and harness evidence are still missing and remain the hard blocker for any true cross-model claim.
