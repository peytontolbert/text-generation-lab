# Stage8950 Registry Frontier Normalization Gate

Passed: `True`

This stage classifies recent failures caused by rerunning frontier-strict builders after the registry moved. It normalizes the frontier without authorizing runtime, converter execution, checkpoint access, decoder CE, denoise CE, mining, or training.

Stale frontier rows: `1`
Passed source rows: `4`
