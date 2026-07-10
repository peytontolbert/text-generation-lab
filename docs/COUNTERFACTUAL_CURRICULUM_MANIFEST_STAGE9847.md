# Stage9847 Counterfactual Curriculum Manifest

Passed: `True`
Rows: `64`
Split counts: `{'eval': 8, 'strict_eval': 8, 'train': 48}`
Role counts: `{'contradictory_evidence': 20, 'evidence_removed': 20, 'mixed_replay': 12, 'positive_original': 12}`

This stage converts the restored counterfactual bank into a heldout curriculum so the 100M model can train on the missing-evidence and contradictory-evidence behaviors instead of being judged on them without exposure.

Next: Run the counterfactual curriculum directly through the 100M structured loop and compare it against Gemma on heldout evidence-removed and contradictory-evidence roots.

