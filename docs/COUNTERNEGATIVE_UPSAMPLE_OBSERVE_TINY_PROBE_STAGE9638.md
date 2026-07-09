# Stage9638 Counternegative Upsample Observe Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.7642857142857142` / `0.2857142857142857`
Strict field exact: `{'episode_boundary_match': 0.14285714285714285, 'episode_failure_type': 0.14285714285714285, 'episode_repair_outcome': 0.2857142857142857, 'episode_step_value': 0.42857142857142855, 'episode_target_prefix_match': 0.42857142857142855}`
Wrong by field: `{'episode_boundary_match': 30, 'episode_failure_type': 32, 'episode_repair_outcome': 27, 'episode_step_value': 22, 'episode_target_prefix_match': 22}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9638 passes, use the episode-step head as an observe-phase repair gate before more denoise; if it fails, inspect wrong_by_field and build the next hard-negative patch.
