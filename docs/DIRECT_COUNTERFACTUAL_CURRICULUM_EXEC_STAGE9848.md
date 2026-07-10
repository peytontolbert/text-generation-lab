# Stage9848 Direct Counterfactual Curriculum Exec

Passed: `True`
Runtime executed: `True`
Row artifacts present: `True`

This stage trains the 100M model on a heldout curriculum that includes the harder counterfactual roles instead of leaving them out of training entirely.

Next: Compare this curriculum-trained 100M run against same-surface Gemma on the heldout harder packet to see whether explicit training on missing-evidence and contradictory-evidence behavior creates a real multilingual edge.
