# Stage9470 Episode Observation Diagnosis Checkpoint-Selection Preflight Audit

Passed: `True`
Execution authorized for next stage: `True`
Eval interval: `8`
Caps: `{'max_decoder_tokens': 768, 'max_eval_rows': 1, 'max_steps': 96, 'max_strict_rows': 1, 'max_train_rows': 48}`

Pass only if any checkpoint or final state has eval_joint_proxy_exact == 1.0 and strict_joint_proxy_exact == 1.0 with no high-confidence wrong rows; no checkpoint is exported.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
