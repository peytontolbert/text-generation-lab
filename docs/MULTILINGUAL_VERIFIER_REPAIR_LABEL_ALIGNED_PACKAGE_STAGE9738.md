# Stage9738 Multilingual Verifier Repair Label-Aligned Package

Passed: `True`
Rows: `108`
Labels: `['DIAGNOSE_FAILURE', 'LOCALIZE_FAILURE', 'REPAIR_API_CALL', 'REPAIR_ASSERTION', 'REPAIR_IMPORT', 'REPAIR_SYNTAX', 'RERUN_VERIFIER', 'RETRIEVE_MORE', 'ROLLBACK_OR_ABSTAIN']`
Language counts: `{'c_cpp': 27, 'python': 27, 'rust': 27, 'web_js_ts_html': 27}`
Split counts: `{'eval': 36, 'strict_eval': 36, 'train': 36}`

This package removes the train/eval label mismatch present in the earlier tiny package by selecting one row for every label in every language and every split.

Next: Run Stage9739 target-100M execution on the label-aligned multilingual verifier-repair package and compare against both the Stage9729 baseline and the Stage9731 longer-step sweep.
