# Stage9771 Edit Localization Visible Evidence Lift Package

Passed: `True`
Rows: `60`
Improved language/split buckets: `12`

This package lifts non-label literal locality evidence into `input_state` so the recovered encoder surface can actually see the distinctions that the target-only baseline was hiding.

Anti-cheat notes:
- target label literals are not lifted
- action sequence and file plan are not lifted
- locality signal ids are not lifted
- raw source and source row ids remain hidden

Next: Train and compare a 100M edit-localization run on the visible-evidence-lift package, then verify whether it breaks the current 0.2 multilingual tie against deterministic Gemma.
