# Stage10023 Current Python A-Only Gap Successor Request

Passed: `True`
Rows: `115`
Python train signatures: `5`

Materialized an A-only signature-safe Python-gap successor manifest that preserves the replay pattern which fixed the blocked A eval rows in stage10022 while removing the D replay rows that failed to improve D and contributed to multilingual regression.

Next: Run the next direct 100M probe on this 115-row manifest; it keeps only the Python A-case replay that improved blocked eval rows in stage10022 while dropping the D-case replay that added pressure without helping D.
