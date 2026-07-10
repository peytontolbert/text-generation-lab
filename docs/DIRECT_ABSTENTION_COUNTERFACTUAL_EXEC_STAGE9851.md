# Stage9851 Direct Abstention Counterfactual Exec

Passed: `True`
Runtime executed: `True`
Row artifacts present: `True`

This stage trains the 100M model on a heldout curriculum that uses an explicit abstention target for missing-evidence rows.

Next: Compare this abstention-target 100M run against same-surface Gemma on the heldout harder packet to see whether explicit abstention improves the multilingual frontier.
