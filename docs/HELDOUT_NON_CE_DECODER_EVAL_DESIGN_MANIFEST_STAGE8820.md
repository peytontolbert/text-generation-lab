# Stage8820 Heldout Non-CE Decoder Eval Design Manifest

Passed: `True`

Rows: `240`
Split counts: `{'eval': 120, 'strict': 120}`
Probe-ready rows: `0`
Decoder CE eligible now rows: `0`
Loss rows: `0`

This design avoids duplicate eval/strict CE targets by requiring future model-output packet checks instead of CE target scoring. It opens no execution or scoring authority.
