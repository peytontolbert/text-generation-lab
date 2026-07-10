# Stage9790 Edit Localization Opaque Choice Surface

Passed: `True`
Rows: `60`
Python strict unique choice orders: `1`

This package is a direct successor to the Stage9771 visible-evidence surface. It preserves visible locality evidence but replaces the raw TARGET_* decoder vocabulary with opaque option tokens A-E, using a deterministic per-language permutation shared across splits.

Anti-cheat notes:
- raw TARGET_* labels are removed from prompt-visible fields
- decoder targets are opaque option tokens only
- candidate options are permuted per row

Next: Run the 100M and Gemma comparison again on the Stage9790 opaque-choice surface, because this package removes the raw TARGET_* label vocabulary that blocked a clean anti-shortcut pass on Stage9771.

