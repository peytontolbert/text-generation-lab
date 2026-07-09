# Stage9704 Symbol-Binding Rebalanced Target-100M Execution

Stage9704 executed the repaired source-backed symbol-binding probe on the recovered target-100M transformer with native grouped ablations enabled.

## Result

- Execution boundary passed: `True`
- Quality passed: `False`
- Eval exact: `0.25`
- Strict exact: `0.25`
- Prediction collapse label: `BIND_CALL_TO_SYMBOL`
- Missing train labels in used batches: `['RETRIEVE_MORE']`

The run remained safe, but the 8-step scheduler underexposed train labels and never trained on `RETRIEVE_MORE`. Fix the sampler before another target-100M run.
