# Stage9944 Web Targeted Refresh Packet

Passed: `True`
Rows: `12`
Surface counts: `{'entrypoint_or_invocation_surface': 3, 'implementation_file_surface': 3, 'symbol_definition_or_implementation_surface': 3, 'test_surface': 3}`
Split counts: `{'eval': 4, 'strict_eval': 4, 'train': 4}`
Weight sum: `30`

Built a targeted web refresh packet from the live edit-localization source manifest that isolates the three currently missed web semantics and preserves one symbol-owner anchor row per split under the existing opaque-choice anti-cheat structure.

Next: Blend this targeted web refresh packet into the next valid 100M edit-localization cycle so test-surface, entrypoint-surface, and implementation-file rows are oversampled while symbol-owner rows remain as anchors.
