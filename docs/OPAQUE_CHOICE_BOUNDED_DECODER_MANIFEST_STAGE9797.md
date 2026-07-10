# Stage9797 Opaque Choice Bounded Decoder Manifest

Passed: `True`
Rows: `60`
Splits: `{'eval': 20, 'strict_eval': 20, 'train': 20}`
Languages: `{'c_cpp': 15, 'python': 15, 'rust': 15, 'web_js_ts_html': 15}`
Decoder labels: `{'A': 12, 'B': 12, 'C': 12, 'D': 12, 'E': 12}`

This stage keeps the corrected Stage9790 visible evidence but rewrites the rows into decoder-CE training shape so bounded decoder execution can learn the opaque A-E labels directly.

Next: Run a bounded decoder CE preexecution contract on the Stage9797 manifest, then execute one real target-100M probe if the contract passes.

