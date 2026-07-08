# Stage9476 Episode Observation Diagnosis Best-State Probe Audit

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Final eval joint: `1.0`
Final strict joint: `1.0`
Best state selection: `{'checkpoint_exported': False, 'enabled': True, 'eval_joint_proxy_exact': 1.0, 'eval_loss': 0.00408231932669878, 'promotion_ready': False, 'restored': True, 'selected_step': 88, 'selection_rule': 'min_eval_plus_strict_loss_among_eval_and_strict_joint_exact_1', 'selection_score': 0.08108809310942888, 'strict_joint_proxy_exact': 1.0, 'strict_loss': 0.0770057737827301}`
Checkpoint-like artifacts: `[]`

In-memory best-state restore converts the balanced-order target-100M episode observation diagnosis probe from final-weight drift to final eval/strict joint exact. This remains a tiny structured-head result, not decoder readiness.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
