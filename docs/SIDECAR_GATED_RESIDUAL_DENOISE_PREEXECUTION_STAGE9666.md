# Stage9666 Sidecar-Gated Residual Denoise Preexecution

Passed: `True`
Rows: `26`
Splits: `{'train': 20, 'eval': 3, 'strict_eval': 3}`
Loss counts: `{'denoise_ce': 26}`

This stage materializes the 26 real Stage9561 residual denoise candidates into denoise-trainer-ready rows by exposing the corrupted output and placing the clean target only in `target.decoder_text`.

Only the next tiny denoise probe is authorized. Decoder CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.

Next: If Stage9666 passes, execute Stage9667 sidecar-gated 26-row real residual denoise target-100M probe and audit exact/contentful/leak/repetition metrics.
