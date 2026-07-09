# Stage9650 Same-Prefix Contrast Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.5` / `0.5`
Eval field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Strict field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Wrong by field: `{'episode_boundary_match': 4, 'episode_target_prefix_match': 4}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9650 passes, widen to a 24-row same-prefix contrast probe; if it fails, inspect structured head direction and consider direct comparator feature injection.
