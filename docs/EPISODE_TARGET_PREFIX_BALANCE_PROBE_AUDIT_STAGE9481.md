# Stage9481 Episode Target-Prefix Balance Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Final eval joint: `1.0`
Final strict joint: `0.5`
High-confidence wrong rows: `[{'cell_key': 'cpp::episode_target_prefix_balance_repair::KEEP_EPISODE_TARGET_PREFIX_BALANCE', 'confidence': 0.9853218793869019, 'correct': False, 'entropy': 0.07653209567070007, 'field': 'episode_target_prefix_match', 'high_confidence_wrong': True, 'margin': 0.9706437420099974, 'pred': 'false', 'pred_index': 0, 'row_id': 'stage9479_target_prefix_balance_0025', 'split': 'strict_eval', 'step': None, 'target': 'true', 'target_index': 1, 'top1_label': 'false', 'top1_logit': 2.0243782997131348, 'top2_label': 'true', 'top2_logit': -2.1822309494018555, 'top_k': [{'label': 'false', 'logit': 2.0243782997131348, 'prob': 0.9853218793869019}, {'label': 'true', 'logit': -2.1822309494018555, 'prob': 0.014678137376904488}]}]`

Focused target-prefix head is safe but not quality-passing. The remaining strict error is a high-confidence false prediction on the CPP positive target-prefix row, indicating sparse positive coverage for non-Rust languages rather than a generic optimizer issue.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
