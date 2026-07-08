# Stage9474 Episode Observation Diagnosis Balanced-Order Probe Audit

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Both-exact checkpoints: `[{'step': 24, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.6468884944915771, 'strict_loss': 0.6726770401000977}, {'step': 48, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.23208296298980713, 'strict_loss': 0.5860256552696228}, {'step': 56, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.016619263216853142, 'strict_loss': 0.2488381713628769}, {'step': 64, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.003307117149233818, 'strict_loss': 0.14015011489391327}, {'step': 88, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.00408231932669878, 'strict_loss': 0.0770057737827301}]`
Selected checkpoint proxy: `{'step': 88, 'eval_joint': 1.0, 'strict_joint': 1.0, 'eval_loss': 0.00408231932669878, 'strict_loss': 0.0770057737827301}`
Final eval joint: `1.0`
Final strict joint: `0.0`

Balanced train ordering produces multiple jointly exact eval/strict intervals, but final weights drift. Next trainer patch should support early-stop/checkpoint-selection telemetry or temporary best-state restore without promotion/export.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
