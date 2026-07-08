# Stage9453 Episode-Step Head/Vocab Design

Passed: `True`

Episode-step supervision should use structured heads for outcome, failure type, boundary match, prefix match, and value proxy. It must not reopen decoder CE from suffix-repair rows.

Next: patch model/training-loop support, then audit statically before any training authorization.
