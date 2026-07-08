# Stage9244 Source-Backed Argument/Context-Balanced Bounded Decoder Tiny Package

Passed: `True`

Rows: `64`
Splits: `{'eval': 16, 'strict_eval': 16, 'train': 32}`
Languages: `{'cpp': 16, 'python': 16, 'rust': 16, 'web_js_ts_html': 16}`
Split-language counts: `{'eval:cpp': 4, 'eval:python': 4, 'eval:rust': 4, 'eval:web_js_ts_html': 4, 'strict_eval:cpp': 4, 'strict_eval:python': 4, 'strict_eval:rust': 4, 'strict_eval:web_js_ts_html': 4, 'train:cpp': 8, 'train:python': 8, 'train:rust': 8, 'train:web_js_ts_html': 8}`
Split argument counts: `{'eval:ARG_CALL': 4, 'eval:ARG_IMPORT': 3, 'eval:ARG_LITERAL': 3, 'eval:ARG_NAME': 3, 'eval:ARG_PATH': 3, 'strict_eval:ARG_CALL': 3, 'strict_eval:ARG_IMPORT': 3, 'strict_eval:ARG_LITERAL': 4, 'strict_eval:ARG_NAME': 3, 'strict_eval:ARG_PATH': 3, 'train:ARG_CALL': 7, 'train:ARG_IMPORT': 7, 'train:ARG_LITERAL': 6, 'train:ARG_NAME': 6, 'train:ARG_PATH': 6}`
Split context counts: `{'eval:add_import_plan': 3, 'eval:callsite_plan': 3, 'eval:hold_plan': 3, 'eval:literal_plan': 3, 'eval:name_plan': 2, 'eval:path_plan': 2, 'strict_eval:add_import_plan': 2, 'strict_eval:callsite_plan': 3, 'strict_eval:hold_plan': 3, 'strict_eval:literal_plan': 3, 'strict_eval:name_plan': 3, 'strict_eval:path_plan': 2, 'train:add_import_plan': 6, 'train:callsite_plan': 6, 'train:hold_plan': 5, 'train:literal_plan': 5, 'train:name_plan': 5, 'train:path_plan': 5}`
Split argument balance deltas: `{'train': 1, 'eval': 1, 'strict_eval': 1}`
Split context balance deltas: `{'train': 1, 'eval': 1, 'strict_eval': 1}`
Authority rows: `0`
Unsafe loss rows: `0`
Target-ref placeholder rows: `0`
Target text copied to input rows: `0`

Stage9240 fixed language coverage but left argument type and context group correlated with split selection. Stage9244 keeps the same tiny caps while balancing those decoder argument factors before any target-100M execution review is reused.

Next: Run target-100M contract-only preflight on Stage9244, then create a fresh inactive execution review if it passes.

