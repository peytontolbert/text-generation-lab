# Stage9628 Hard-Phrase Tri-Phase Regression Audit

Passed: `True`
Stage9623 contentful / prefix: `0.5` / `0.16666666666666666`
Stage9627 contentful / prefix: `0.08333333333333333` / `0.08333333333333333`
Stage9627 repetition / unterminated: `0.9166666666666666` / `0.9166666666666666`

Decision: reject Stage9625 hard-phrase warm-up as a curriculum branch. It preserved safety but created a stronger repetition attractor.

Next: Return to the Stage9623 tri-phase baseline and design a non-generative anti-repetition/EOS continuation objective or decoding-time repetition guard audit before further denoise execution.
