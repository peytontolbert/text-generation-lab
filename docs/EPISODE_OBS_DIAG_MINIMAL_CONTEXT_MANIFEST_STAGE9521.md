# Stage9521 Episode Observation Diagnosis Minimal-Context Manifest

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Language counts: `{'rust': 36, 'python': 5, 'cpp': 13, 'web_js_ts_html': 4}`
Loss counts: `{'episode_failure_type_ce': 58, 'episode_repair_outcome_ce': 58, 'episode_step_value_mse': 58}`

This manifest keeps controlled language/route/action context and primitive `obs_*` verifier features, while redacting literal generation prefix text.
