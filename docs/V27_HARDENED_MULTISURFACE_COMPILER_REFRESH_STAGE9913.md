# Stage9913 V2.7 Hardened Multisurface Compiler Refresh

Passed: `True`
Rows: `444`
Skill counts: `{'bounded_argument_rendering': 64, 'edit_localization': 48, 'patch_operator_selection': 144, 'symbol_binding': 80, 'verifier_failure_repair_or_abstain': 108}`
Loss counts: `{'decoder_ce': 64, 'edit_localization_ce': 48, 'patch_operator_ce': 144, 'symbol_binding_ce': 80, 'verifier_repair_ce': 108}`

This stage refreshes the real v2.7 multisurface mix with the hardened edit-localization source: the no-label-list opaque-choice packet that beat Gemma on the same surface now replaces the older geometry-aware remap packet.

Next: Use this hardened compiled package as the next real v2.7 training mix: edit localization now comes from the no-label-list opaque-choice packet that beat Gemma on all 8 same-surface buckets.
