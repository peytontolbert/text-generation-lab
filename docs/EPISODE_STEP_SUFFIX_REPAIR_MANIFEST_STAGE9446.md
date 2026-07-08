# Stage9446 Episode-Step Suffix Repair Manifest

Passed: `True`
Rows: `50`
Splits: `{'eval': 1, 'strict_eval': 1, 'train': 48}`
Outcomes: `{'residual_suffix_repair_step': 29, 'successful_suffix_repair_step': 21}`

This manifest recasts the gated suffix repair probe as episode-step transitions. It is not trainable yet: all decoder CE, denoise CE, runtime reward, model execution, and promotion authority remain closed.
