# Stage9483 Target-Prefix Observe-Phase Boundary Design

Passed: `True`
Current encoder observation-visible rows: `0`
Current contradictory encoder inputs: `0`

Do not continue treating episode_target_prefix_match as a pure pre-action policy target. It is a verifier/observation-phase target and should either be computed deterministically by the verifier or trained with an observe-phase input packet that exposes generated output evidence without exposing the label string.

Stage9482 positive rows remain useful, but they must be materialized as observe/verify-phase examples with generated-output evidence or as deterministic verifier fixtures, not as hidden-observation pre-action rows.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
