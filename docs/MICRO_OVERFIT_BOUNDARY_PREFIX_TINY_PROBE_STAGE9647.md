# Stage9647 Micro-Overfit Boundary Prefix Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.5` / `0.0`
Eval field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Strict field exact: `{'episode_boundary_match': 0.0, 'episode_target_prefix_match': 0.0}`
Wrong by field: `{'episode_boundary_match': 6, 'episode_target_prefix_match': 6}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9647 passes, widen to a 24-row boundary/prefix manifest; if it fails, inspect module deltas and label vocab direction before changing data again.
