# Stage10101 Real Session Edit Localization Bootstrap Shortcut Audit

Passed: `True`
Rows scanned: `56`
Unique target rows: `19`
Unique target counts: `{'TARGET_FILE': 19}`
Changed-path signature majority exact: `1.0`

This stage audits the real augmented session inventory identified in stage10100. The result is that the inventory is useful as a real source evidence reservoir, but it is not yet a fair edit-localization eval packet: uniquely targetable rows collapse to `TARGET_FILE`, and changed-path signatures alone recover those labels perfectly.

Next: Do not score this inventory directly as edit localization. Use it as a source evidence reservoir, then build explicit candidate competition and anti-shortcut controls so the answer is not recoverable from changed-path signatures alone.
