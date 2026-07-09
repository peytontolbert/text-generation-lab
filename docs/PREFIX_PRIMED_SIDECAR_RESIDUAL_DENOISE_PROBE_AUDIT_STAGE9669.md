# Stage9669 Prefix-Primed Sidecar Residual Denoise Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Exact rows: `0` / `26`
Target-prefix rows: `3` / `26`
Generation-prefix-start rows: `26` / `26`
Contentful rows: `26` / `26`
Short/junk rows: `0`
Repetition rows: `0`
Internal leak rows: `0`

Prefix priming worked mechanically, but the model still selected generic post-prefix continuations instead of the discriminating suffix tokens.

Top first mismatches: `{'localized=>reference': 5, 'wrapper=>answer': 4, 'the=>should': 4, 'localized=>path': 3, 'relevant=>relevant.': 2, 'checked=>evidence': 2, 'receive=>rece': 2, 'keeps=>matches': 2, 'an=>': 1, 'preserves=>should': 1}`

Next: Build Stage9670 post-prefix suffix-choice/slot discriminator manifest from Stage9669 mismatches; keep decoder/runtime/Gemma/harness closed.
