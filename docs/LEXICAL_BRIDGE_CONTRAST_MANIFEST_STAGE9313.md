# Stage9313 Lexical Bridge Contrast Manifest

Passed: `True`
Rows: `12`
Bridge counts: `{'bridge_a': 5, 'bridge_b': 7}`
Variant counts: `{'clean_prefix_to_required_bridge_continuation': 8, 'observed_bad_bridge_to_clean_target': 4}`
Bridge IDs are opaque in model-visible fields: `bridge_a` and `bridge_b`.
Externally, these target the two Stage9312 residual failures: `keeps` -> `keeps the patch inside` and `verified patch operator` vs `operatch`/`expected assertion`.
No model execution, decoder CE, runtime, Gemma, harness, source/body emission, scoring, or promotion is authorized.
