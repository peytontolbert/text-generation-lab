# Stage9888 Current Margin Position Bias Diagnostics

Passed: `True`
Source target positions: `{'K': {3: 6, 2: 6}, 'M': {0: 4, 4: 3, 1: 2, 2: 3}, 'R': {4: 7, 1: 2, 0: 3}, 'T': {0: 3, 4: 3, 1: 6}}`
Debiased target positions: `{'K': {1: 3, 3: 3, 2: 4, 4: 1, 0: 1}, 'M': {0: 2, 3: 2, 1: 2, 4: 3, 2: 3}, 'R': {0: 3, 2: 1, 1: 3, 3: 4, 4: 1}, 'T': {0: 3, 4: 5, 2: 2, 3: 2}}`
K prediction counts: `{'R': 8}`

The current multilingual counterfactual guard packet still contains target-token and semantic-surface position skew, including narrow support for K. Stage9888 materializes a position-debiased variant for a like-for-like multilingual rerun.

Next: Run Stage9889 on the position-debiased current-frontier manifest, then compare whether K exact rises above 0.0 and whether multilingual strict exact recovers without reintroducing shortcut-sensitive gains.

