# Stage9381 Bounded Decoder CE Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `0` / `16`
Contentful rows: `4` / `16`
Target-prefix rows: `0` / `16`
Repetition rows: `12`
Unterminated rows: `11`
Short/junk rows: `0`
Leak rows: `0`
Eval loss: `46.14628601074219`
Strict eval loss: `46.860260009765625`

Decoder CE reopened only for the tiny audited probe. The result is not quality-passing, so the next step returns failures to denoise repair rather than scaling CE.
