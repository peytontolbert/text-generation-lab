# Stage9294 One-Next-Token Suffix Probe Audit

Stage9294 executed the tiny target-100M one-next-token suffix denoise probe.

Safety gate passed: True
Quality gate passed: False
Train one-token generation passed: False
Train loss: 84.38444519042969 -> 2.012596607208252
Eval loss: 63.30027389526367
Strict eval loss: 9.530162811279297
Generation prefix start rate: 1.0
Target prefix match rate: 0.0
Unterminated rate: 1.0
Degenerate repetition rate: 0.0
Internal token leak rows: 0
Diagnosis: one_next_token_free_run_suffix_generation_fails_despite_teacher_forced_loss_drop

Decoder CE, runtime, Gemma, harness, scoring, source/body emission, checkpoint export, and promotion remained closed.
