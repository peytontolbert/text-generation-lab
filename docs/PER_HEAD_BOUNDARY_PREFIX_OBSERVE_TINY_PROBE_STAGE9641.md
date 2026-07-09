# Stage9641 Per-Head Boundary Prefix Observe Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.7142857142857143` / `0.42857142857142855`
Eval field exact: `{'episode_boundary_match': 0.6428571428571429, 'episode_target_prefix_match': 0.7857142857142857}`
Strict field exact: `{'episode_boundary_match': 0.42857142857142855, 'episode_target_prefix_match': 0.42857142857142855}`
Wrong by field: `{'episode_boundary_match': 26, 'episode_target_prefix_match': 22}`
High-confidence wrong rows: `48`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9641 passes, add repair_outcome in a separate two-head follow-up; if it fails, inspect boundary/prefix wrong pairs and patch the per-head contrast set before recombining objectives.
