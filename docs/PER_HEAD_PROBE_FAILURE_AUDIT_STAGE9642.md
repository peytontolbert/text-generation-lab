# Stage9642 Per-Head Probe Failure Audit

Passed: `True`
Strict field exact: `{'episode_boundary_match': 0.42857142857142855, 'episode_target_prefix_match': 0.42857142857142855}`
High-confidence wrong rows: `48`
Label by split: `{'train': {'episode_boundary_match': {'True': 12, 'False': 16}, 'episode_target_prefix_match': {'False': 22, 'True': 6}}, 'eval': {'episode_boundary_match': {'False': 18, 'True': 10}, 'episode_target_prefix_match': {'False': 22, 'True': 6}}, 'strict_eval': {'episode_boundary_match': {'False': 12, 'True': 16}, 'episode_target_prefix_match': {'False': 12, 'True': 16}}}`
Top wrong pairs: `{'strict_eval::episode_boundary_match::true=>false': 16, 'strict_eval::episode_target_prefix_match::true=>false': 16, 'eval::episode_boundary_match::true=>false': 10, 'eval::episode_target_prefix_match::true=>false': 6}`

The isolated two-head probe still learned a high-confidence false default. Train/eval were prefix-negative heavy while strict was positive-heavy, so strict positives failed as true=>false. The next manifest should balance true/false labels per split for both boundary and prefix, with counterpositive rows present in train/eval/strict.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Build Stage9643 balanced-positive per-head observe manifest with true/false labels balanced per split for episode_boundary_match and episode_target_prefix_match; run contract/shortcut audit before another tiny probe.
