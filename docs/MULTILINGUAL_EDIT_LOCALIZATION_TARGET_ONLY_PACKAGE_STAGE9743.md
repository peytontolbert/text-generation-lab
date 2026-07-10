# Stage9743 Multilingual Edit Localization Target-Only Package

Passed: `True`
Rows: `60`
Labels: `['TARGET_CONFIG', 'TARGET_ENTRYPOINT', 'TARGET_FILE', 'TARGET_SYMBOL', 'TARGET_TEST']`
Language counts: `{'c_cpp': 15, 'python': 15, 'rust': 15, 'web_js_ts_html': 15}`
Split counts: `{'eval': 20, 'strict_eval': 20, 'train': 20}`

This package removes the abstention and retrieval labels that dominated the repaired full-label run while keeping concrete localization targets balanced across languages and splits.

Next: Run Stage9744 target-100M execution on the target-only multilingual edit-localization package and compare it against the full-label Stage9733 baseline.
