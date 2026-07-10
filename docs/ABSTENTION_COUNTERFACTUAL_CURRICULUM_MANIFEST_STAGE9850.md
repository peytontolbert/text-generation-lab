# Stage9850 Abstention Counterfactual Curriculum Manifest

Passed: `True`
Rows: `64`
Split counts: `{'eval': 8, 'strict_eval': 8, 'train': 48}`
Target label counts: `{'A': 12, 'ABSTAIN_INSUFFICIENT_EVIDENCE': 20, 'B': 12, 'C': 8, 'D': 8, 'E': 4}`

This stage changes the hard objective boundary: missing-evidence rows no longer force a guessed localization target and instead train an explicit abstention label.

Next: Run this abstention-target curriculum directly through the 100M structured loop and compare it against Gemma on heldout evidence-removed and contradictory-evidence roots.

