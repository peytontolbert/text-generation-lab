# General KBPP Sweep Readiness

Artifact: `runs/local/artifacts/general_kbpp_sweep_readiness.json`

## Finding

The pilot is useful for validating scoring and tiny-rung representation geometry, but it is far too low-entropy for 10M-100M conclusions. A 100M model can only score 3.994944302478051e-06 KBPP at oracle on this pilot, so the benchmark must expand before it can test whether a 100M general model beats a modern 7B on useful intelligence density.

## Pilot Entropy

- Hidden eval units: `145`
- Hidden eval bits: `399.4944302478051`
- Hidden generalization bits: `301.40923048437935`
- Hidden composition bits: `32.0`
- Depth-weighted hidden bits: `445.6724342479337`

## Parameter Rungs

- `1000` params: oracle KBPP `0.3994944302478051`, generalization KBPP `0.30140923048437934`, composition KBPP `0.032`; role `informative_tiny_geometry_probe`
- `7600` params: oracle KBPP `0.0525650566115533`, generalization KBPP `0.03965910927426044`, composition KBPP `0.004210526315789474`; role `informative_tiny_geometry_probe`
- `10000` params: oracle KBPP `0.03994944302478051`, generalization KBPP `0.030140923048437934`, composition KBPP `0.0032`; role `informative_tiny_geometry_probe`
- `16280` params: oracle KBPP `0.024538969916941347`, generalization KBPP `0.0185140804965835`, composition KBPP `0.0019656019656019656`; role `informative_tiny_geometry_probe`
- `23369` params: oracle KBPP `0.017095058849236386`, generalization KBPP `0.012897823205288175`, composition KBPP `0.0013693354443921435`; role `informative_tiny_geometry_probe`
- `25852` params: oracle KBPP `0.015453134389904267`, generalization KBPP `0.011659029494212415`, composition KBPP `0.001237815256073031`; role `informative_tiny_geometry_probe`
- `100000` params: oracle KBPP `0.003994944302478051`, generalization KBPP `0.0030140923048437933`, composition KBPP `0.00032`; role `sanity_check_only_expand_before_claims`
- `1000000` params: oracle KBPP `0.0003994944302478051`, generalization KBPP `0.00030140923048437934`, composition KBPP `3.2e-05`; role `sanity_check_only_expand_before_claims`
- `10000000` params: oracle KBPP `3.994944302478051e-05`, generalization KBPP `3.0140923048437936e-05`, composition KBPP `3.2e-06`; role `underpowered_benchmark_requires_more_hidden_bits`
- `100000000` params: oracle KBPP `3.994944302478051e-06`, generalization KBPP `3.0140923048437936e-06`, composition KBPP `3.2e-07`; role `underpowered_benchmark_requires_more_hidden_bits`

## Next Target

The next dataset target is at least `10000000` hidden verified bits before using the benchmark to judge 100M-vs-7B density. That is a `25031.638097675186`x increase over the current pilot.
