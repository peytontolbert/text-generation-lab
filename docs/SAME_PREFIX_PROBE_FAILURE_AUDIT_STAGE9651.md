# Stage9651 Same-Prefix Probe Failure Audit

Passed: `True`
Strict field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Confidence bins: `{'low': 16}`
Top wrong pairs: `{'strict_eval::episode_target_prefix_match::false=>true': 2, 'eval::episode_boundary_match::true=>false': 1, 'eval::episode_boundary_match::false=>true': 1, 'eval::episode_target_prefix_match::false=>true': 1, 'eval::episode_target_prefix_match::true=>false': 1, 'strict_eval::episode_boundary_match::false=>true': 1, 'strict_eval::episode_boundary_match::true=>false': 1}`

Same-prefix contrast removed prefix identity as a shortcut, but target-100M stayed at chance with low confidence. The representation likely needs an explicit structured boundary_token_relation feature instead of asking the tiny probe to infer equality from two serialized text fields.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Build Stage9652 comparator-feature micro manifest with boundary_token_relation=same|different, then run contract audit before execution.
