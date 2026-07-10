# Stage9770 Multilingual Edit Localization Gemma Comparison

Passed: `True`
Language count: `4`
100M-better languages: `0`
Gemma-better languages: `0`
Tie languages: `4`

Result summary:
- python: tie at 0.2 strict exact
- rust: tie at 0.2 strict exact
- c_cpp: tie at 0.2 strict exact
- web_js_ts_html: tie at 0.2 strict exact

Anti-cheat note: bounded Gemma artifacts now record full-packet label vocabulary scope and deterministic seeded decoding; the earlier slice-local label collapse and decoding drift issues are no longer part of these results.

Next: Push edit-localization beyond 0.2 with better target-space evidence and disambiguation rows, then expand the same deterministic comparison contract to patch operator and verifier repair before claiming any cross-language Gemma win.
