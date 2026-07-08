# Stage9249 Semantic Bounded Decoder Target Repair Package

Passed: `True`

Rows: `64`
Splits: `{'eval': 16, 'strict_eval': 16, 'train': 32}`
Languages: `{'cpp': 16, 'python': 16, 'rust': 16, 'web_js_ts_html': 16}`
Argument counts: `{'ARG_CALL': 14, 'ARG_IMPORT': 13, 'ARG_LITERAL': 13, 'ARG_NAME': 12, 'ARG_PATH': 12}`
Context counts: `{'add_import_plan': 11, 'callsite_plan': 12, 'hold_plan': 11, 'literal_plan': 11, 'name_plan': 10, 'path_plan': 9}`
Language-prefix rows: `0`
Template phrase rows: `0`
Argument-label echo rows: `0`
First-token dominance rate: `0.281`

This stage repairs the target renderer only. It does not execute the model, train decoder CE, open runtime, emit source bodies, or alter authority.

Next: Run Stage9248-style semantic diversity audit on Stage9249, then contract-only preflight if it passes.

