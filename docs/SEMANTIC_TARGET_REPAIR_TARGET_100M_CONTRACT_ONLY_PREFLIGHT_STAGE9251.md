# Stage9251 Semantic Target Repair Target-100M Contract-Only Preflight

Passed: `True`

Stage9251 reran the bounded decoder CE probe contract check against the Stage9249 semantic target-repaired manifest. This was a contract-only run: no model execution, no decoder CE training, no final checkpoint export, no runtime, no harness, and no Gemma path.

Rows: `64`
Train/eval/strict: `{'eval': 16, 'other': 0, 'strict_eval': 16, 'train': 32}`
Probe scale: `target_100m`
Model execution attempted: `False`
Unsafe loss rows: `0`
Over-cap rows: `0`
Empty target rows: `0`

Next: create a fresh inactive execution review for Stage9249/9251. Actual execution remains closed unless explicitly authorized for one tiny probe.

