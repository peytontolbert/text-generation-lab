# Stage9749 Full Product Harness Gemma Queue

Passed: `True`
Queue entries: `36`
Priority buckets: `{'aligned_with_supported_standalone_cell': 13, 'no_standalone_proxy_support_yet': 23}`
Languages: `{'c_cpp': 9, 'python': 9, 'rust': 9, 'web_js_ts_html': 9}`
Skills: `{'bounded_argument_rendering': 4, 'edit_localization': 4, 'final_user_facing_summary': 4, 'intent_to_build_strategy': 4, 'patch_operator_selection': 4, 'repo_state_graph_navigation': 4, 'symbol_binding': 4, 'verifier_expectation': 4, 'verifier_failure_repair_or_abstain': 4}`
Top queue entry: `full_product_harness::python::symbol_binding`

This stage packages the full-product harness side of the v2.7 comparison problem. It does not run harness or Gemma, but it makes the full harness queue explicit and prioritizes the subset whose standalone analogues already have truthful 100M-side evidence.

Next: When harness and Gemma execution are explicitly opened, start the full-product queue with the 13 cells aligned to supported standalone evidence, then cover the remaining 23 cells that still lack any current 100M-side proxy support.
