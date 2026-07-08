# Stage9478 Episode-Step Full Best-State Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Final eval joint: `0.8`
Final strict joint: `1.0`
Failed eval fields: `['episode_target_prefix_match']`
Both-exact intervals: `[]`

Full five-head episode-step structured probe is safe but not quality-passing. Eval and strict become exact at different intervals; the final residual is eval episode_target_prefix_match. Next patch should balance/counterbalance target-prefix supervision or split full five-head objective from diagnosis heads.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
