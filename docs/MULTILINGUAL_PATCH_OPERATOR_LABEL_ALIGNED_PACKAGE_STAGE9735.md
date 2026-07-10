# Stage9735 Multilingual Patch Operator Label-Aligned Package

Passed: `True`
Rows: `144`
Labels: `['ABSTAIN_UNSAFE', 'ADD_IMPORT', 'ADD_TEST_CASE', 'BUILD_ADAPTER', 'CREATE_FILE', 'INSERT_FUNCTION', 'MODIFY_EXISTING_SYMBOL', 'REPLACE_EXPR', 'RETRIEVE_MORE', 'ROLLBACK_PATCH', 'UPDATE_CONFIG_FIELD', 'WRAP_CALL']`
Language counts: `{'c_cpp': 36, 'python': 36, 'rust': 36, 'web_js_ts_html': 36}`
Split counts: `{'eval': 48, 'strict_eval': 48, 'train': 48}`

This package removes the train/eval label mismatch present in the earlier tiny package by selecting one row for every label in every language and every split.

Next: Run Stage9736 target-100M execution on the label-aligned multilingual patch-operator package and compare against the Stage9729 zero-exact baseline.
