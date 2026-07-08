# Stage9240 Source-Backed Multi-Language Bounded Decoder Tiny Package

Passed: `True`

Rows: `64`
Splits: `{'eval': 16, 'strict_eval': 16, 'train': 32}`
Languages: `{'cpp': 16, 'python': 16, 'rust': 16, 'web_js_ts_html': 16}`
Split-language counts: `{'eval:cpp': 4, 'eval:python': 4, 'eval:rust': 4, 'eval:web_js_ts_html': 4, 'strict_eval:cpp': 4, 'strict_eval:python': 4, 'strict_eval:rust': 4, 'strict_eval:web_js_ts_html': 4, 'train:cpp': 8, 'train:python': 8, 'train:rust': 8, 'train:web_js_ts_html': 8}`
Target hash unique rows: `64`
Cross-split duplicate target hashes: `0`
Authority rows: `0`
Unsafe loss rows: `0`
Target-ref placeholder rows: `0`
Target text copied to input rows: `0`

This stage supersedes the Stage9237 package because Stage9237 was safety-clean but language-imbalanced. Stage9240 enforces Python/Rust/C++/web-TS coverage before any target-100M execution.

Next: Run target-100M contract-only preflight on the Stage9240 balanced manifest, then create a fresh inactive execution review if it passes.

