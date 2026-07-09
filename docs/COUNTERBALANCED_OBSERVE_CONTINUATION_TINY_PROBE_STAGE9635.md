# Stage9635 Counterbalanced Observe Continuation Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.6375` / `0.5`
Strict field exact: `{'episode_boundary_match': 0.25, 'episode_failure_type': 0.25, 'episode_repair_outcome': 0.5, 'episode_step_value': 0.75, 'episode_target_prefix_match': 0.75}`
Wrong by field: `{'episode_boundary_match': 18, 'episode_failure_type': 20, 'episode_repair_outcome': 15, 'episode_step_value': 8, 'episode_target_prefix_match': 8}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9635 passes, use the episode-step head as a routing gate before more denoise; if it fails, inspect wrong_by_field and build the next counterbalance patch.
