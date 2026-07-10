# Stage9741 Label-Aligned Multilingual Structured Surface Comparison

Passed: `True`
Best surface: `edit_localization`
Ranking: `['edit_localization', 'verifier_repair', 'patch_operator']`
Surface metrics: `{'verifier_repair': {'eval_exact': 0.1111111111111111, 'strict_exact': 0.1111111111111111, 'baseline_eval_exact': 0.25, 'baseline_strict_exact': 0.25, 'improved_over_stage9729': False}, 'edit_localization': {'eval_exact': 0.14285714285714285, 'strict_exact': 0.14285714285714285, 'baseline_eval_exact': 0.0, 'baseline_strict_exact': 0.0, 'improved_over_stage9729': True}, 'patch_operator': {'eval_exact': 0.08333333333333333, 'strict_exact': 0.08333333333333333, 'baseline_eval_exact': 0.0, 'baseline_strict_exact': 0.0, 'improved_over_stage9729': True}}`

This stage compares the current executed 100M performance of the three label-aligned multilingual structured surfaces. It is still not a Gemma comparison.

Next: Use the ranked label-aligned structured surfaces to decide which 100M path is strongest enough to package for later same-surface Gemma comparison, while extending the same repair pattern to any remaining weak surfaces.
