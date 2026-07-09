# Stage9560 Residual Denoise Loss-Mask Reopen Design

Passed: `True`
Rows: `44`
Future denoise CE candidate rows: `41`
Rare holdout rows: `3`
Current denoise CE rows: `0`
Proposed denoise CE rows after future authorization: `41`

This is a design-only stage. It does not authorize execution and it does not reopen current losses.
The proposed future loss mask enables `denoise_ce` only for candidate rows; decoder CE, runtime reward, and structured auxiliary losses remain closed.
