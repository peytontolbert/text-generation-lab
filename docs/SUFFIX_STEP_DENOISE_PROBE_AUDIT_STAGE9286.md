# Stage9286 Suffix-Step Denoise Probe Audit

Stage9286 executed the tiny target-100M suffix-step denoise probe.

Safety gate passed: True
Quality gate passed: False
Train loss: 86.53744506835938 -> 24.233970642089844
Eval loss: 84.2314453125
Strict eval loss: 53.77687072753906
Generation prefix start rate: 1.0
Contentful rate: 0.0
Unterminated rate: 1.0
Degenerate repetition rate: 0.3333333333333333
Target prefix match rate: 0.0
Diagnosis: teacher_forcing_loss_decreases_but_eval_strict_suffix_generation_still_fails

Decoder CE, runtime, Gemma, harness, scoring, source/body emission, checkpoint export, and promotion remained closed.
