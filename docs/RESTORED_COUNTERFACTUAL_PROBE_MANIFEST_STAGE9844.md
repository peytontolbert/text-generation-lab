# Stage9844 Restored Counterfactual Probe Manifest

Passed: `True`
Rows: `60`
Split counts: `{'eval': 20, 'strict_eval': 20, 'train': 20}`
Role counts: `{'contradictory_evidence': 20, 'evidence_removed': 20, 'positive_original': 20}`

This stage restores evidence-removed and contradictory-evidence rows that were intentionally dropped from the earlier trainer execution manifest, while still preventing fixed A-E semantic shortcuts inside each bucket.

Next: Run the restored evidence-removed and contradictory-evidence probe through the direct 100M loop and the same-surface Gemma runner so the missing anti-cheat families are measured instead of inferred.

