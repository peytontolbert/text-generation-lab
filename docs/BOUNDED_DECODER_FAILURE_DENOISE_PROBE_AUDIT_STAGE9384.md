# Stage9384 Bounded Decoder Failure Denoise Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact rows: `2` / `23`
Target-prefix rows: `2` / `23`
Contentful rows: `22` / `23`
Repetition rows: `1`
Unterminated rows: `0`
Short/junk rows: `0`
Leak rows: `0`

The repair removed unterminated generation and mostly suppressed repetition, but the target recovery signal is still weak without a generation prefix field.
