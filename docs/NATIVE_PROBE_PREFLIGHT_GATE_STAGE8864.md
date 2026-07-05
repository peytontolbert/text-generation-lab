# Stage8864 Native Probe Preflight Gate

Passed: `True`

This stage defines one candidate tiny structured native probe plan and audits that the plan remains closed-authority.

## Candidate Probe

- mode: `structured_policy_probe`
- objective: `intent_to_build_strategy`
- caps: train 32, eval 16, strict 16, steps 8
- losses: structured aux only; decoder CE and denoise are `0.0`
- output root: `runs/local/probes/...`
- post-run gate: `scripts/native_probe_interpretability_artifact_contract.py --mode structured_aux_probe`

## Boundary

No model execution, decoder CE, denoise CE, runtime, Gemma, harness/scoring, source/body emission, controller merge, repository mining, or promotion is authorized by this stage.

If the future Stage8869 probe is explicitly run, its output must pass the Stage8862 artifact contract before any metric can be trusted.
