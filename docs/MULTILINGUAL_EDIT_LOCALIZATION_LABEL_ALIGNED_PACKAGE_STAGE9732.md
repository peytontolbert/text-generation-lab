# Stage9732 Multilingual Edit Localization Label-Aligned Package

Passed: `True`
Rows: `84`
Labels: `['ABSTAIN_UNBOUND', 'RETRIEVE_MORE', 'TARGET_CONFIG', 'TARGET_ENTRYPOINT', 'TARGET_FILE', 'TARGET_SYMBOL', 'TARGET_TEST']`
Language counts: `{'c_cpp': 21, 'python': 21, 'rust': 21, 'web_js_ts_html': 21}`
Split counts: `{'eval': 28, 'strict_eval': 28, 'train': 28}`

This package removes the train/eval label mismatch present in the earlier tiny package by selecting one row for every label in every language and every split.

Next: Run Stage9733 target-100M execution on the label-aligned multilingual edit-localization package and compare against the Stage9729 zero-exact baseline.
