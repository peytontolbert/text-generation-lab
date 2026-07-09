# Stage9566 Residual Denoise Target-Rendered Manifest

Passed: `True`
Rows: `41`
Rendered targets: `{'REPAIR_PREFIX_AND_BOUNDARY :: not_exact+target_prefix_miss+boundary_next_token_miss': 17, 'REPAIR_PREFIX_ONLY :: not_exact+target_prefix_miss': 24}`

This stage fixes the Stage9564 EOS-only target bug by writing a bounded `target.decoder_text`/`target.label` consumed by the trainer.
