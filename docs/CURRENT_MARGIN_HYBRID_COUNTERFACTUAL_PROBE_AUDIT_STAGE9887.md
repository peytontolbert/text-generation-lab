# Stage9887 Current Margin Hybrid Counterfactual Probe Audit

Passed: `True`
Eval exact: `0.4375`
Strict exact: `0.5`
Delta vs Stage9883 eval: `0.0`
Delta vs Stage9883 strict: `0.0`
Confusion identical to Stage9883: `True`
Per-cell exact identical to Stage9883: `True`

The Stage9885 hybrid strict-anchor rerun is executable and contract-clean, but it is behaviorally identical to Stage9883 on exact accuracy, per-language cell exact, and confusion structure. The K-to-R collapse persists, so the strict-anchor swap does not improve the multilingual frontier.

Next: Do not promote the Stage9885 hybrid path. Attack the persistent K-to-R collapse upstream with evidence or objective changes on the main current-frontier path before rerunning Gemma comparisons.

