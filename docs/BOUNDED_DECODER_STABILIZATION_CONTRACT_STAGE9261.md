# Stage9261 Bounded Decoder Stabilization Contract

Stage9253 proved the recovered target-100M transformer path executes and receives decoder CE gradients, but generation failed.

Required next changes:

- Add `--eos-loss-weight` and EOS-position token-loss telemetry.
- Record post-clip gradient norm separately from raw pre-clip norm.
- Materialize generated repetition failures as negative/stabilization rows.
- Add EOS/length bucket audit by language and surface.
- Rerun at lower LR (`1e-5`) with the same tiny row caps before any scale-up.

Blocked until those patches exist: second target-100M bounded decoder execution, row scale-up, Gemma comparison, harness scoring, and checkpoint promotion.
