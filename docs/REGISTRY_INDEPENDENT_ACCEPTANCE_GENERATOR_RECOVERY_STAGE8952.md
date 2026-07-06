# Stage8952 Registry-Independent Acceptance Generator Recovery

Passed: `True`

This stage recovers converter acceptance-test generation from the stable Stage8948 fixture source without relying on the mutable registry latest pointer. It emits metadata-only test-spec rows and records stale-frontier failures as registry hygiene, not execution readiness.

Test spec rows: `5`
Stale frontier rows: `3`
